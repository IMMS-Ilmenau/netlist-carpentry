"""Base structure of the `Module` class."""

from collections import defaultdict
from typing import TYPE_CHECKING, Callable, DefaultDict, Dict, List, Optional, Tuple, Union, overload

from typing_extensions import Self

from netlist_carpentry import Instance, Port, Wire
from netlist_carpentry.core.enums.element_type import EType
from netlist_carpentry.core.exceptions import ObjectNotFoundError, PathResolutionError
from netlist_carpentry.core.netlist_elements.element_path import (
    T_PATH_TYPES,
    ElementPath,
    InstancePath,
    ModulePath,
    PortPath,
    PortSegmentPath,
    WirePath,
    WireSegmentPath,
)
from netlist_carpentry.core.netlist_elements.netlist_element import NetlistElement
from netlist_carpentry.core.netlist_elements.port_segment import PortSegment
from netlist_carpentry.core.netlist_elements.wire_segment import CONST_MAP_VAL2OBJ, WireSegment
from netlist_carpentry.utils.custom_dict import CustomDict

if TYPE_CHECKING:
    from netlist_carpentry import Circuit, Module


T_MODULE_PARTS = Union[Instance, Port['Module'], Port[Instance], PortSegment, Wire, WireSegment]
T_PORT = Union[Port['Module'], Port[Instance]]


class ModuleBaseMixin(NetlistElement):
    _circuit: Optional['Circuit'] = None
    _instances = CustomDict[str, Instance]()
    _ports = CustomDict[str, Port['Module']]()
    _wires = CustomDict[str, Wire]()

    @property
    def path(self) -> ModulePath:
        """
        Returns the ModulePath of the netlist element.

        The ModulePath object is constructed using the element's type and its raw hierarchical path.

        Returns:
            ModulePath: The hierarchical path of the netlist element.
        """
        return ModulePath(raw=self.raw_path)

    @property
    def type(self) -> EType:
        """The type of the element, which is a module."""
        return EType.MODULE

    @property
    def circuit(self) -> 'Circuit':
        if self._circuit is not None:
            return self._circuit
        raise ObjectNotFoundError(f'No circuit set for module {self.raw_path}!')

    @property
    def instances(self) -> CustomDict[str, Instance]:
        """
        Returns the instances of this module as a dictionary.

        In the dictionary, the key is the instance's name and the value is the associated instance object.
        """
        return self._instances

    @property
    def instances_by_types(self) -> DefaultDict[str, List[Instance]]:
        """
        Returns a dictionary where keys are instance types and values are lists of instances of that type.

        This method groups all instances in the module by their respective instance types.
        """
        inst_dict = defaultdict(list)
        for inst in self.instances.values():
            inst_dict[inst.instance_type].append(inst)
        return inst_dict

    @property
    def ports(self) -> CustomDict[str, Port['Module']]:
        """
        Returns the ports of this module as a dictionary.

        In the dictionary, the key is the port's name and the value is the associated port object.
        """
        return self._ports

    @property
    def wires(self) -> CustomDict[str, Wire]:
        """
        Returns the wires of this module as a dictionary.

        In the dictionary, the key is the wire's name and the value is the associated wire object.
        """
        return self._wires

    @property
    def input_ports(self) -> List[Port['Module']]:
        """
        Returns a list of input ports in the module.

        This property filters the ports based on their direction, returning only those with an input direction.
        """
        return [p for p in self.ports.values() if p.is_input]

    @property
    def output_ports(self) -> List[Port['Module']]:
        """
        Returns a list of output ports in the module.

        This property filters the ports based on their direction, returning only those with an output direction.
        """
        return [p for p in self.ports.values() if p.is_output]

    @property
    def instances_with_constant_inputs(self) -> List[Instance]:
        """A list of Instance objects where at least one input port is tied to a constant."""
        return [i for i in self.instances.values() if i.has_tied_inputs()]

    @property
    def submodules(self) -> List[Instance]:
        """A list of submodule instances in the module."""
        return [i for i in self.instances.values() if i.is_module_instance]

    @property
    def primitives(self) -> List[Instance]:
        """A list of instances marked as primitive in the module."""
        return [i for i in self.instances.values() if i.is_primitive]

    @property
    def gatelib_primitives(self) -> List[Instance]:
        """A list of primitive instances in the module that are based on gates from the gate library."""
        return [i for i in self.instances.values() if i.is_primitive]

    def valid_module_path(self, path: ElementPath) -> bool:
        """
        Checks whether the given element path is a valid module path.

        Args:
            path (ElementPath): The path to be validated.

        Returns:
            bool: True if the path is valid, False otherwise.
        """
        return path.get(0) == self.name

    def is_in_module(self, path: ElementPath) -> bool:
        """
        Checks whether an element with the given path exists within this module.

        Args:
            path (ElementPath): The path of the element to be searched for.

        Returns:
            bool: True if the element is found within the module, False otherwise.
        """
        try:
            self.get_from_path(path)
            return True
        except PathResolutionError:
            return False

    @overload
    def get_from_path(self, path: InstancePath) -> Instance: ...
    @overload
    def get_from_path(self, path: PortPath) -> T_PORT: ...
    @overload
    def get_from_path(self, path: PortSegmentPath) -> PortSegment: ...
    @overload
    def get_from_path(self, path: WirePath) -> Wire: ...
    @overload
    def get_from_path(self, path: WireSegmentPath) -> WireSegment: ...
    @overload
    def get_from_path(self, path: ElementPath) -> NetlistElement: ...
    def get_from_path(self, path: T_PATH_TYPES) -> Union[NetlistElement, T_MODULE_PARTS]:
        """
        Retrieves the NetlistElement from the given ElementPath.

        If the path points to outside of this module (i.e. the element, to which the path points, is not part of this module),
        returns None.

        Args:
            path: The path to the element.

        Returns:
            A NetlistElement matching the given path) if it is part of this module and has been found, otherwise raises an error.

        Raises:
            PathResolutionError: If the path could not be resolved.
        """
        if self.valid_module_path(path):
            return self._get_from_path_in_module(path)
        elif isinstance(path, WireSegmentPath) and path.raw in CONST_MAP_VAL2OBJ:
            return CONST_MAP_VAL2OBJ[path.raw]
        raise PathResolutionError(f'Path {path} points outside of this module {self.name}!')

    def _get_from_path_in_module(self, path: ElementPath) -> NetlistElement:
        """
        Retrieve a netlist element from a given path within the current module.

        Args:
            path (ElementPath): The path to the element.

        Returns:
            NetlistElement: The element at the specified path, or raises an error if not found.

        Raises:
            PathResolutionError: If the path could not be resolved.
        """
        mapping: Dict[type[ElementPath], Tuple[Callable[..., T_MODULE_PARTS], Union[ElementPath, str]]] = {
            PortPath: (self._get_port_from_path, path),
            PortSegmentPath: (self._get_port_segment, path),
            WirePath: (self.wires.get, path.name),
            WireSegmentPath: (self._get_wire_segment, path),
            InstancePath: (self.instances.get, path.name),
        }
        if type(path) in mapping:  # type: ignore[misc]
            method, args = mapping.get(type(path))  # type: ignore[misc]
            obj: T_MODULE_PARTS = method(args)
            if obj is not None:
                return obj
        raise PathResolutionError(f'Unable to find an object of type {path.type} with path {path.raw} in module {self.name}!')

    def _get_port_segment(self, ps_path: PortSegmentPath) -> PortSegment:
        """
        Retrieves a specific port segment within the module.

        Args:
            ps_path (PortSegmentPath): The path to the port segment.

        Returns:
            PortSegment: A PortSegment object representing the specified port segment if found, otherwise None.
        """
        if not ps_path.name.isnumeric():
            raise PathResolutionError(f'Last element of {ps_path} must be a numeric value (segment index)!')
        return self._get_port_from_path(ps_path)[int(ps_path.name)]

    def _get_wire_segment(self, ws_path: WireSegmentPath) -> WireSegment:
        """
        Retrieves a specific wire segment within the module.

        Args:
            ws_path (WireSegmentPath): The path to the wire segment.

        Returns:
            WireSegment: A WireSegment object representing the specified wire segment if found, otherwise None.
        """
        if not ws_path.name.isnumeric():
            raise PathResolutionError(f'Last element of {ws_path} must be a numeric value (segment index)!')
        return self.wires[ws_path.parent.name][int(ws_path.name)]

    @overload
    def _get_port_from_path(self, element_path: PortPath) -> T_PORT: ...
    @overload
    def _get_port_from_path(self, element_path: PortSegmentPath) -> T_PORT: ...
    def _get_port_from_path(self, element_path: Union[PortPath, PortSegmentPath]) -> Optional[T_PORT]:
        """
        Retrieves a port from a given path.

        This method handles paths for both module ports and instance ports.
        It checks the path to determine whether it points to a port on the current module or an instance port within the module.

        Args:
            element_path (PortPath): The path to the port.

        Returns:
            A Port object representing the specified port if found, otherwise None.
        """
        # For module ports   +  port segments:  module.port.port_segment            ==> pholder_idx = -3 ("module"), port_idx = -2 ("port")
        # For instance ports +  port segments:  module.instance.port.port_segment   ==> pholder_idx = -3 ("instance"), port_idx = -2 ("port")
        # For module ports   +  ports:          module.port                         ==> pholder_idx = -2 ("module"), port_idx = -1 ("port")
        # For instance ports +  ports:          module.instance.port                ==> pholder_idx = -2 ("instance"), port_idx = -1 ("port")
        (port_holder_idx, port_idx) = (-2, -1) if isinstance(element_path, PortPath) else (-3, -2)
        try:
            if element_path.get(port_holder_idx) == self.name:
                return self.ports[element_path.get(port_idx)]
            inst = self.instances[element_path.get(port_holder_idx)]
            return inst.ports[element_path.get(port_idx)]
        except KeyError:
            raise PathResolutionError(f'Unable to find an object of type {element_path.type} with path {element_path.raw} in module {self.name}!')

    def _set_name_recursively(self, old_name: str, new_name: str) -> None:
        for p in self.ports.values():
            p.raw_path = p.path.replace(old_name, new_name).raw
            for _, ps in p:
                ps.raw_path = ps.path.replace(old_name, new_name).raw
                ps.set_ws_path(ps.ws_path.replace(old_name, new_name).raw)
        for w in self.wires.values():
            w.raw_path = w.path.replace(old_name, new_name).raw
            for _, ws in w:
                ws.raw_path = ws.path.replace(old_name, new_name).raw
                for ps in ws.port_segments:
                    ps.raw_path = ps.path.replace(old_name, new_name).raw
        for i in self.instances.values():
            i.raw_path = i.path.replace(old_name, new_name).raw
            for pi in i.ports.values():
                pi.raw_path = pi.path.replace(old_name, new_name).raw
                for _, s in pi:
                    s.raw_path = s.path.replace(old_name, new_name).raw
                    s.set_ws_path(s.ws_path.replace(old_name, new_name).raw)

    def change_mutability(self, is_now_locked: bool, recursive: bool = False) -> Self:
        """
        Change the mutability of this Module instance.

        Args:
            is_now_locked (bool): The new value for this module's mutability.
                True means, the module is now immutable; False means, the module is mow mutable.
            recursive (bool, optional): Whether to also update mutability for all subordinate elements,
                e.g. instances, ports and wires that are part of this module. Defaults to False.

        Returns:
            Module: This instance with its mutability changed.
        """
        if recursive:
            for p in self.ports.values():
                p.change_mutability(is_now_locked=is_now_locked)
            for w in self.wires.values():
                w.change_mutability(is_now_locked=is_now_locked)
            for i in self.instances.values():
                i.change_mutability(is_now_locked=is_now_locked)
        return super().change_mutability(is_now_locked)

    def __str__(self) -> str:
        return f'{self.__class__.__name__} "{self.name}"'

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.name})'
