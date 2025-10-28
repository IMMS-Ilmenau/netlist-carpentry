from typing import Dict, Union, overload

from netlist_carpentry.core.netlist_elements.element_path import (
    T_PATH_TYPES,
    ElementPath,
    InstancePath,
    PortPath,
    PortSegmentPath,
    WirePath,
    WireSegmentPath,
)
from netlist_carpentry.core.netlist_elements.instance import Instance
from netlist_carpentry.core.netlist_elements.netlist_element import NetlistElement
from netlist_carpentry.core.netlist_elements.port import Port
from netlist_carpentry.core.netlist_elements.port_segment import PortSegment
from netlist_carpentry.core.netlist_elements.wire import Wire
from netlist_carpentry.core.netlist_elements.wire_segment import WireSegment

T_MODULE_PARTS = Union[Instance, Port, PortSegment, Wire, WireSegment]


class ModuleBaseMixin(NetlistElement):
    @property
    def instances(self) -> Dict[str, Instance]:
        raise NotImplementedError(f'Not implemented for mixin {self.__class__.__name__}. Any class using this mixin must implement this property.')

    @property
    def ports(self) -> Dict[str, Port]:
        raise NotImplementedError(f'Not implemented for mixin {self.__class__.__name__}. Any class using this mixin must implement this property.')

    @property
    def wires(self) -> Dict[str, Wire]:
        raise NotImplementedError(f'Not implemented for mixin {self.__class__.__name__}. Any class using this mixin must implement this property.')

    @overload
    def get_from_path(self, element_path: InstancePath) -> Instance: ...
    @overload
    def get_from_path(self, element_path: PortPath) -> Port: ...
    @overload
    def get_from_path(self, element_path: PortSegmentPath) -> PortSegment: ...
    @overload
    def get_from_path(self, element_path: WirePath) -> Wire: ...
    @overload
    def get_from_path(self, element_path: WireSegmentPath) -> WireSegment: ...
    def get_from_path(self, element_path: T_PATH_TYPES) -> T_MODULE_PARTS:
        raise NotImplementedError(f'Not implemented for mixin class {self.__class__.__name__}')

    def is_in_module(self, element_path: ElementPath) -> bool:
        raise NotImplementedError(f'Not implemented for mixin class {self.__class__.__name__}')
