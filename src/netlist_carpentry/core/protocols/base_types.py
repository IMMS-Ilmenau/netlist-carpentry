from typing import Protocol

from netlist_carpentry.core.port_direction import PortDirection


class Connectable(Protocol):
    @property
    def is_connected(self) -> bool: ...
    @property
    def is_unconnected(self) -> bool: ...


class ConnectableMultibit(Connectable, Protocol):
    @property
    def is_connected_partly(self) -> bool: ...
    @property
    def is_unconnected_partly(self) -> bool: ...


class DirectedElement(Protocol):
    @property
    def is_input(self) -> bool: ...
    @property
    def is_output(self) -> bool: ...
    @property
    def direction(self) -> PortDirection: ...


class DirectedPortElement(DirectedElement, Protocol):
    @property
    def is_instance_port(self) -> bool: ...
    @property
    def is_module_port(self) -> bool: ...
    @property
    def is_driver(self) -> bool: ...
    @property
    def is_load(self) -> bool: ...
