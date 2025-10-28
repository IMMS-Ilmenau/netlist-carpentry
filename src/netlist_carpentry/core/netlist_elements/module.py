from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, List, Literal, Optional, Set, Tuple, Type, TypeVar, Union, overload

import networkx as nx
from pydantic import BaseModel, NonNegativeInt, PositiveInt
from typing_extensions import Self

from netlist_carpentry import LOG
from netlist_carpentry.core.exceptions import (
    AlreadyConnectedError,
    InvalidPortDirectionError,
    ObjectLockedError,
    ObjectNotFoundError,
    PathResolutionError,
    WidthMismatchError,
)
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
from netlist_carpentry.core.netlist_elements.element_type import EType
from netlist_carpentry.core.netlist_elements.instance import Instance
from netlist_carpentry.core.netlist_elements.mixins.evaluation import EvaluationMixin
from netlist_carpentry.core.netlist_elements.mixins.graph_building import GraphBuildingMixin
from netlist_carpentry.core.netlist_elements.mixins.metadata import METADATA_DICT, NESTED_DICT
from netlist_carpentry.core.netlist_elements.mixins.module_base import T_MODULE_PARTS
from netlist_carpentry.core.netlist_elements.mixins.module_bfs import ModuleBfsMixin
from netlist_carpentry.core.netlist_elements.mixins.module_dfs import ModuleDfsMixin
from netlist_carpentry.core.netlist_elements.netlist_element import NetlistElement
from netlist_carpentry.core.netlist_elements.port import Port
from netlist_carpentry.core.netlist_elements.port_segment import PortSegment
from netlist_carpentry.core.netlist_elements.wire import Wire
from netlist_carpentry.core.netlist_elements.wire_segment import CONST_MAP_VAL2OBJ, WireSegment
from netlist_carpentry.core.port_direction import PortDirection
from netlist_carpentry.utils.custom_dict import CustomDict
from netlist_carpentry.utils.custom_list import CustomList

T_NETLIST_ELEMENT = TypeVar('T_NETLIST_ELEMENT', bound=NetlistElement)
T_INSTANCE = TypeVar('T_INSTANCE', bound=Instance)
T_PORT = Union[Port['Module'], Port[Instance]]


class Module(GraphBuildingMixin, EvaluationMixin, ModuleBfsMixin, ModuleDfsMixin, NetlistElement, BaseModel):
    _instances = CustomDict[str, Instance]()
    _ports = CustomDict[str, Port['Module']]()
    _wires = CustomDict[str, Wire]()
    _wire_gen_i: int = 0
    _inst_gen_i: int = 0
    _list_len: int = 0

    def model_post_init(self, __context: Optional[Dict[str, object]]) -> None:
        self._graph: nx.MultiDiGraph[str] = self.build_graph()
        self._prev_hash: int = hash(self)
        return super().model_post_init(__context)

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, Module):
            return NotImplemented
        if not super().__eq__(value):
            return False
        return self.instances == value.instances and self.ports == value.ports and self.wires == value.wires

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
    def instances(self) -> CustomDict[str, Instance]:
        """
        Returns the instances of this module as a dictionary.

        In the dictionary, the key is the instance's name and the value is the associated instance object.
        """
        return self._instances

    @property
    def instances_by_types(self) -> CustomDict[str, List[Instance]]:
        """
        Returns a dictionary where keys are instance types and values are lists of instances of that type.

        This method groups all instances in the module by their respective instance types.
        """
        inst_dict = CustomDict[str, List[Instance]]()
        for inst in self.instances.values():
            inst_dict.append_or_create(inst.instance_type, inst)  # type: ignore[arg-type]
        return inst_dict

    @property
    def ports(self) -> CustomDict[str, Port[Module]]:
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
    def input_ports(self) -> Set[Port[Module]]:
        """
        Returns a set of input ports in the module.

        This property filters the ports based on their direction, returning only those with an input direction.

        Returns:
            A set of Port objects representing the input ports.
        """
        return {p for p in self.ports.values() if p.is_input}

    @property
    def output_ports(self) -> Set[Port[Module]]:
        """
        Returns a set of output ports in the module.

        This property filters the ports based on their direction, returning only those with an output direction.

        Returns:
            A set of Port objects representing the output ports.
        """
        return {p for p in self.ports.values() if p.is_output}

    @property
    def instances_with_constant_inputs(self) -> Set[Instance]:
        """A set of Instance objects where at least one input port is tied to a constant."""
        return {i for i in self.instances.values() if i.has_tied_inputs()}

    @property
    def submodules(self) -> Set[Instance]:
        """A set of submodule instances in the module."""
        return {i for i in self.instances.values() if i.is_module_instance}

    @property
    def primitives(self) -> Set[Instance]:
        """A set of instances marked as primitive in the module."""
        return {i for i in self.instances.values() if i.is_primitive}

    @property
    def gatelib_primitives(self) -> Set[Instance]:
        """A set of primitive instances in the module that are based on gates from the gate library."""
        return {i for i in self.instances.values() if i.is_primitive_from_gatelib}

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
        if type(path) in mapping:
            method, args = mapping.get(type(path))
            obj = method(args)
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
    def _get_port_from_path(self, element_path: Union[PortPath, PortSegmentPath]) -> T_PORT:
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
        if element_path.get(port_holder_idx) == self.name:
            return self.get_port(element_path.get(port_idx))
        inst = self.get_instance(element_path.get(port_holder_idx))
        return inst.ports.get(element_path.get(port_idx))

    def add_instance(self, instance: T_INSTANCE) -> T_INSTANCE:
        """
        Adds an instance to the module.

        Args:
            instance (Instance): The instance to be added.

        Returns:
            Instance: the instance that was added.
        """
        return self.instances.add(instance.name, instance, locked=self.locked)

    @overload
    def create_instance(
        self, interface_definition: Type[T_INSTANCE], instance_name: Optional[str] = None, params: Dict[str, object] = {}
    ) -> T_INSTANCE: ...
    @overload
    def create_instance(self, interface_definition: Module, instance_name: Optional[str] = None, params: Dict[str, object] = {}) -> Instance: ...

    def create_instance(
        self, interface_definition: Union[Module, Type[T_INSTANCE]], instance_name: Optional[str] = None, params: Dict[str, object] = {}
    ) -> Instance:
        """
        Creates an instance within this module based on the given interface definition, instance name and parameters.

        If `interface_definition` is a module, this creates a submodule instance inside this module, based on the given
        instance name and module definition.

        If `interface_definition` is a **class** (not an instance) that extends `netlist_carpentry.Instance` (e.g. a gate
        from the internal gate library), this creates a primitive gate instance inside this module.

        The instance type of the created instance is either the name of the provided module or the type of the provided instance class.
        The instance is thus linked to either the module definition or the type of the given instance by its own instance type.

        Args:
            interface_definition (Union[Module, Instance]): The module whose interface is to be copied to the new instance.
                Alternatively, the primitive instance **class**, whose interface is to be copied to the new instance.
            instance_name (str): The target name of the instance to be created.
            params (Dict[str, object]): A dictionary containing parameters for the instance to be created

        Returns:
            Instance: The instance that was created and added.
        """
        if instance_name is None:
            instance_name = self._get_generic_inst_name(interface_definition)
        if isinstance(interface_definition, Module):
            inst = Instance(raw_path=self.raw_path + self.path.sep + instance_name, instance_type=interface_definition.name, module=self)
            for pname, p in interface_definition.ports.items():
                inst.connect(pname, ws_path=None, direction=p.direction, width=p.width)
        else:
            inst = interface_definition(raw_path=self.raw_path + self.path.sep + instance_name, module=self, **params)
        return self.add_instance(inst)

    def _get_generic_inst_name(self, module_or_inst_cls: Union[Module, Type[Instance]]) -> str:
        type_abbrev = module_or_inst_cls.name if isinstance(module_or_inst_cls, Module) else module_or_inst_cls.__name__
        while f'_{type_abbrev}_{self._inst_gen_i}_' in self.instances:
            self._inst_gen_i += 1
        return f'_{type_abbrev}_{self._inst_gen_i}_'

    @overload
    def remove_instance(self, instance: str) -> None: ...
    @overload
    def remove_instance(self, instance: Instance) -> None: ...

    def remove_instance(self, instance: Union[str, Instance]) -> None:
        """
        Removes an instance from the module.

        Args:
            instance (Union[str, Instance}): The name of the instance to be removed, or the Instance object itself.
        """
        instance_name = instance.name if isinstance(instance, Instance) else instance
        if instance_name in self.instances:
            for p in self.instances[instance_name].ports.values():
                for _, ps in p:
                    self.disconnect(ps)
        self.instances.remove(instance_name, locked=self.locked)

    def get_instance(self, instance_name: str) -> Optional[Instance]:
        """
        Retrieves an instance by its name.

        Guarded alternative to Module.instances[instance_name], with fallback to return None if not found.

        Args:
            instance_name (str): The name of the instance to be retrieved.

        Returns:
            Optional[Instance]: The instance with the specified name if found, otherwise None.
        """
        return self.instances.get(instance_name, None)

    def get_instances(self, name: str = '', type: str = '', fuzzy: bool = False) -> List[Instance]:
        """
        Retrieves a list of instances based on the given criteria.

        Args:
            name (str, optional): The name of the instance to be searched for. Defaults to ''.
            type (str, optional): The type of the instance to be searched for. Defaults to ''.
            fuzzy (bool, optional): Whether to perform a fuzzy search or not. Defaults to False.

        Returns:
            List[Instance]: A list of instances matching the specified criteria.
        """
        nr_set_args = sum([bool(name), bool(type)])
        if nr_set_args > 1:
            LOG.warn(f'Only one argument of "name" or "type" must be set to get instances, but {nr_set_args} arguments were set!')
            return []
        if name:
            return [self.instances[i_name] for i_name in self.instances if (name in i_name and fuzzy) or (name == i_name)]
        if type:
            inst_list = CustomList(
                [self.instances_by_types[i_type] for i_type in self.instances_by_types if (type in i_type and fuzzy) or (type == i_type)]
            )
            return inst_list.flatten()
        LOG.warn(f'At least "name" or "type" must be set to get instances, but name was "{name}" and type was "{type}"!')
        return []

    def add_port(self, port: Port[Module]) -> Port[Module]:
        """
        Adds a port to the module.

        Args:
            port (Port): The port to be added.

        Returns:
            Port: The port that was added.
        """
        return self.ports.add(port.name, port, locked=self.locked)

    def create_port(
        self,
        port_name: str,
        direction: PortDirection = PortDirection.UNKNOWN,
        width: int = 1,
        offset: int = 0,
        is_locked: bool = False,
    ) -> Port[Module]:
        """
        Creates a new port within the module and connects it to the specified wire segments.

        Returns the port object, if it was created successfully (i.e. no port with the same name exists already), or None otherwise.
        If the port was not created (because it already exists), the provided wire segment paths are ignored.

        Args:
            port_name (str): The name of the port to be created.
            direction (PortDirection, optional): The direction of the port. Defaults to PortDirection.UNKNOWN.
            width (int, optional): The width of the port. Defaults to 1, which means the port is 1 bit wide.
            offset (int, optional): The index offset for port slices. Defaults to 0, which means the port indexing starts at 0.
            is_locked (bool, optional): Whether the port should be unchangeable after creation or not. Defaults to False.

        Returns:
            Optional[Port]: The port if the port was successfully created and added, None otherwise (if a port with this name already exists).
        """
        # first use add/create wire and then call this function
        # this function automatically connects the ports to the wires provided in wire_connection_paths
        e = f'{self.path.raw}.{port_name}'
        p = Port(raw_path=e, direction=direction, module_or_instance=self)
        self.add_port(p)
        p.create_port_segments(width, offset)
        p.change_mutability(is_now_locked=is_locked)
        LOG.info(f'Created port {self.name}.{port_name}, {width} bit wide.')
        return p

    @overload
    def remove_port(self, port: str) -> None: ...
    @overload
    def remove_port(self, port: Port[Module]) -> None: ...

    def remove_port(self, port: Union[str, Port[Module]]) -> None:
        """
        Removes a port from the module.

        Args:
            port (Union[str, Port]): The name of the port to be removed, or the Port object itself.
        """
        port_name = port.name if isinstance(port, Port) else port
        if port_name in self.ports:
            for _, ps in self.ports[port_name]:
                self.disconnect(ps.path)
        self.ports.remove(port_name, locked=self.locked)

    def get_port(self, port_name: str) -> Optional[Port[Module]]:
        """
        Retrieves a port by its name.

        Guarded alternative to Module.port[port_name], with fallback to return None if not found.

        Args:
            port_name (str): The name of the port to be retrieved.

        Returns:
            Port: The port with the specified name if found, otherwise None.
        """
        return self.ports.get(port_name, None)

    def get_ports(self, name: str = '', direction: Optional[PortDirection] = None, fuzzy: bool = False) -> List[Port[Module]]:
        """
        Retrieves a list of ports based on the given criteria.

        Args:
            name (str, optional): The name of the port to be searched for. Defaults to ''.
            direction (PortDirection, optional): The direction of the port to be searched for. Defaults to None.
            fuzzy (bool, optional): Whether to perform a fuzzy search or not. Defaults to False.

        Returns:
            List[Port]: A list of ports matching the specified criteria.
        """
        nr_set_args = sum([bool(name), direction is not None])
        if nr_set_args > 1:
            LOG.warn(f'Only one argument of "name" or "direction" must be set to get ports, but {nr_set_args} arguments were set!')
            return []
        if name:
            return [self.ports[p_name] for p_name in self.ports if (name in p_name and fuzzy) or (name == p_name)]
        if direction is not None:
            return [
                self.ports[p_name]
                for p_name in self.ports
                if (fuzzy and self._fuzzy_direction(direction, self.ports[p_name].direction)) or (self.ports[p_name].direction == direction)
            ]
        LOG.warn(f'At least "name" or "direction" must be set to get ports, but name was "{name}" and direction was "{direction}"!')
        return []

    def _fuzzy_direction(self, target_dir: PortDirection, found_dir: PortDirection) -> bool:
        """
        Checks if a port direction matches the target direction in a fuzzy manner.

        Args:
            target_dir (PortDirection): The target direction to be matched.
            found_dir (PortDirection): The direction of the port being checked.

        Returns:
            bool: True if the port direction matches the target direction, False otherwise.
        """
        return target_dir == found_dir or found_dir == PortDirection.IN_OUT

    def add_wire(self, wire: Wire) -> Wire:
        """
        Adds a wire to the module.

        Args:
            wire (Wire): The wire to be added.

        Returns:
            Wire: The wire that was added.
        """
        return self.wires.add(wire.name, wire, locked=self.locked)

    def create_wire(self, wire_name: Optional[str] = None, width: PositiveInt = 1, is_locked: bool = False, index_offset: int = 0) -> Wire:
        """
        Creates a new wire within the module.

        Returns the wire object, if it was created successfully (i.e. no wire with the same name exists already), or None otherwise.

        Args:
            wire_name (Optional[str]): The name of the wire to be created. Defaults to None, in which case a generic wire is created.
                In this case, the name of the wire is `_ncgen_{index}_`.
            width (PositiveInt, optional): The number of segments in the wire. Defaults to 1.
            is_locked (bool, optional): Whether the wire should be unchangeable after creation or not. Defaults to False.
            index_offset (int, optional): The offset for the segment indices. Defaults to 0.

        Returns:
            Optional[Wire]: The wire if the wire was successfully created and added, None otherwise (if a wire with this name already exists).
        """
        if not wire_name:
            return self._create_generic_wire(width, is_locked, index_offset)
        e = f'{self.path.raw}.{wire_name}'
        w = Wire(raw_path=e, module=self)
        w.create_wire_segments(width, index_offset)
        w.change_mutability(is_now_locked=is_locked)
        return self.add_wire(w)

    def _create_generic_wire(self, width: PositiveInt = 1, is_locked: bool = False, index_offset: NonNegativeInt = 0) -> Wire:
        """
        Creates a new wire with a generic name within the module and returns the wire object.

        Args:
            width (PositiveInt, optional): The number of segments in the wire. Defaults to 1.
            is_locked (bool, optional): Whether the wire should be unchangeable after creation or not. Defaults to False.
            index_offset (NonNegativeInt, optional): The offset for the segment indices. Defaults to 0.

        Returns:
            Wire: The created wire.
        """
        while f'_ncgen_{self._wire_gen_i}_' in self.wires:
            self._wire_gen_i += 1
        gen_name = f'_ncgen_{self._wire_gen_i}_'
        return self.create_wire(gen_name, width=width, is_locked=is_locked, index_offset=index_offset)

    @overload
    def remove_wire(self, wire: str) -> None: ...
    @overload
    def remove_wire(self, wire: Wire) -> None: ...

    def remove_wire(self, wire: Union[str, Wire]) -> None:
        """
        Removes a wire from the module.

        Args:
            wire (Union[str, Wire]): The name of the wire to be removed, or the Wire object itself.
        """
        wire_name = wire.name if isinstance(wire, Wire) else wire
        if wire_name in self.wires:
            for p in self.wires[wire_name].connected_port_segments:
                self.disconnect(p.path)
        self.wires.remove(wire_name, locked=self.locked)

    def get_wire(self, wire_name: str) -> Optional[Wire]:
        """
        Retrieves a wire by its name.

        Guarded alternative to Module.wires[wire_name], with fallback to return None if not found.

        Args:
            wire_name (str): The name of the wire to be retrieved.

        Returns:
            Wire: The wire with the specified name if found, otherwise None.
        """
        return self.wires.get(wire_name, None)

    def get_wires(self, name: str = '', fuzzy: bool = False) -> List[Wire]:
        """
        Retrieves a list of wires based on the given criteria.

        Args:
            name (str, optional): The name of the wire to be searched for. Defaults to ''.
            fuzzy (bool, optional): Whether to perform a fuzzy search or not. Defaults to False.

        Returns:
            List[Wire]: A list of wires matching the specified criteria.
        """
        if name:
            return [self.wires[w_name] for w_name in self.wires if (name in w_name and fuzzy) or (name == w_name)]
        LOG.warn(f'A "name" must be set to get wires, but name was "{name}"!')
        return []

    @overload
    def connect(
        self, source: Union[PortSegmentPath, PortSegment], target: Union[PortSegmentPath, PortSegment], new_wire_name: Optional[str] = None
    ) -> None: ...
    @overload
    def connect(self, source: Union[PortPath, T_PORT], target: Union[PortPath, T_PORT], new_wire_name: Optional[str] = None) -> None: ...
    @overload
    def connect(
        self, source: Union[WireSegmentPath, WireSegment], target: Union[PortSegmentPath, PortSegment], new_wire_name: Optional[str] = None
    ) -> None: ...
    @overload
    def connect(self, source: Wire, target: T_PORT, new_wire_name: Optional[str] = None) -> None: ...

    def connect(
        self,
        source: Union[PortSegmentPath, PortPath, PortSegment, T_PORT, WireSegmentPath, WireSegment, Wire],
        target: Union[PortSegmentPath, PortPath, PortSegment, T_PORT],
        new_wire_name: Optional[str] = None,
    ) -> None:
        # First, get objects from path
        source_obj = self._get_from_path_or_object(source)
        target_obj = self._get_from_path_or_object(target)
        if not target_obj.is_unconnected:
            raise AlreadyConnectedError(f'{target_obj.type.value} {target_obj.raw_path} must be unconnected before attempting to connect it!')
        if isinstance(source_obj, WireSegment) or isinstance(source_obj, Wire):
            return self._connect_p2w(source_obj, target_obj)
        if isinstance(source_obj, Port) and isinstance(target_obj, Port):
            return self._connect_ports_full(source_obj, target_obj, new_wire_name=new_wire_name)
        w = self.create_wire(new_wire_name) if source_obj.is_unconnected else source_obj.ws_path
        self.connect(w, source_obj)
        self.connect(w, target_obj)

    @overload
    def _get_from_path_or_object(self, path_or_object: InstancePath) -> Instance: ...
    @overload
    def _get_from_path_or_object(self, path_or_object: PortPath) -> T_PORT: ...
    @overload
    def _get_from_path_or_object(self, path_or_object: PortSegmentPath) -> PortSegment: ...
    @overload
    def _get_from_path_or_object(self, path_or_object: WirePath) -> Wire: ...
    @overload
    def _get_from_path_or_object(self, path_or_object: WireSegmentPath) -> WireSegment: ...
    @overload
    def _get_from_path_or_object(self, path_or_object: T_NETLIST_ELEMENT) -> T_NETLIST_ELEMENT: ...
    def _get_from_path_or_object(self, path_or_object: Union[T_PATH_TYPES, T_NETLIST_ELEMENT]) -> T_NETLIST_ELEMENT:
        """
        Returns the corresponding NetlistElement for a given path, or returns the given NetlistElement.

        If a path is provided, resolve it and return the object to which the path points.
        If an object is given, do nothing and return the object.
        The main reason for this method is to unify element paths and elements to simplify type handling.

        Args:
            path_or_object: The path to the element.

        Returns:
            A NetlistElement (matching the given path) or the given element (if it is already a NetlistElement).
        """
        if isinstance(path_or_object, ElementPath):
            return self.get_from_path(path_or_object)
        return path_or_object

    def _connect_ports_full(self, driver: T_PORT, load: T_PORT, new_wire_name: Optional[str] = None) -> None:
        if load.is_driver:
            raise InvalidPortDirectionError(f'Received a signal driving port {load.raw_path}, but expected a load!')
        if driver.width != load.width:
            raise WidthMismatchError(
                f'Connection failed: Port {driver.raw_path} is {driver.width} bit wide and port {load.raw_path} is {load.width} bit wide. '
                + 'Consider explicit bitwise connection of each port_segment:port_segment instead of port:port in such cases. '
                + 'Example:\n\tconnect(port.segment[0], port.segment[3])\n\tconnect(port.segment[1], port.segment[4])'
            )

        if driver.is_unconnected_partly:
            w = self.create_wire(new_wire_name, width=driver.width)
        for idx, dr_seg in driver:
            ws = dr_seg.ws_path if dr_seg.is_connected else w[idx]
            if dr_seg.is_unconnected:
                self.connect(ws, dr_seg)  # Only if a new wire was created
            self.connect(ws, load[idx + load.offset])

    def _connect_p2w(self, wire_like: Union[WireSegment, Wire], port_like: Union[PortSegment, T_PORT]) -> None:
        """
        Connects a wire segment and a port segment.

        Args:
            wire_like (Union[WireSegment, Wire]): The wire segment to be connected.
                Also accepts wires, but then requires an equally wide port as counterpart.
            port_like (Union[PortSegment, Port]): The port segment to be connected.
                Also accepts ports, but then requires an equally wide wire as counterpart.
        """
        if isinstance(wire_like, Wire) and isinstance(port_like, Port):
            if wire_like.width != port_like.width:
                raise WidthMismatchError(
                    f'Connection failed: Wire {wire_like.raw_path} is {wire_like.width} bit wide and port {port_like.raw_path} is {port_like.width} bit wide. '
                    + 'Consider explicit bitwise connection of each wire_segment:port_segment instead of wire:port in such cases. '
                    + 'Example:\n\tconnect(wire.segment[0], port.segment[3])\n\tconnect(wire.segment[1], port.segment[4])'
                )
            for idx in wire_like.segments:
                self.connect(wire_like[idx], port_like[idx])
            return
        if isinstance(wire_like, Wire) and wire_like.width == 1:
            w = wire_like[wire_like.offset]  # equal to wire[0] in most cases
        else:
            w = wire_like
        if isinstance(port_like, Port) and port_like.width == 1:
            p = port_like[port_like.offset]  # equal to port[0] in most cases
        else:
            p = port_like
        if p.locked or w.locked or self.locked:
            LOG.error(f'Unable to connect port segment at {p.raw_path} to wire segment {w.raw_path} in module {self.name}: locked object!')
            return
        self._connect_to_wire_segment(p, w)

    def _connect_to_wire_segment(self, p: PortSegment, w: WireSegment) -> None:
        """
        Connects a port segment and a wire segment.

        This method connects the given port segment to the given wire segment.

        Args:
            p (PortSegment): The port segment to be connected.
            w (WireSegment): The wire segment to be connected.
        """
        # Connect Wire -> Port
        if p not in w.port_segments:
            w.port_segments.append(p)
        w.notify_listeners()
        # Connect Port -> Wire
        if p.parent_parent_name == self.name:
            # Connect a module port segment to a wire segment
            p.set_ws_path(w.raw_path)
            p.notify_listeners()
        else:
            # Connect an instance port segment to a wire segment
            inst = self.instances[p.parent_parent_name]
            inst.modify_connection(p.parent_name, w.path, index=p.index)

    @overload
    def disconnect(self, port_like: PortSegmentPath) -> None: ...
    @overload
    def disconnect(self, port_like: PortSegment) -> None: ...
    @overload
    def disconnect(self, port_like: T_PORT) -> None: ...

    def disconnect(self, port_like: Union[PortSegmentPath, PortSegment, T_PORT]) -> None:
        """
        Disconnects a port segment from its connected wire segment.

        Args:
            port_like (Union[PortSegmentPath, PortSegment]): The path of the port segment to be disconnected, or the PortSegment itself.
                Also accepts ports, aqd will then disconnect the complete port.
        """
        if isinstance(port_like, Port):
            return self._disconnect_port(port_like)
        elif isinstance(port_like, PortSegmentPath):
            p = self.get_from_path(port_like)
            if p is None:
                raise ObjectNotFoundError(f'Unable to disconnect port at {port_like.raw} in module {self.name}: no such element!')
        else:
            p = port_like
        w = self.get_from_path(p.ws_path)
        if p.locked or (w.locked and not w.is_constant) or self.locked:
            raise ObjectLockedError(
                f'Unable to disconnect port segment at {p.raw_path} from wire segment {w.raw_path} in module {self.name}: locked object!'
            )
        self._disconnect(p, w)

    def _disconnect_port(self, p: T_PORT) -> None:
        """
        Disconnects a whole port from its connected wire segments.

        This method removes all connection from the given port.

        Args:
            p (Port): The port to be disconnected.
        """
        for _, s in p:
            self.disconnect(s)

    def _disconnect(self, p: PortSegment, w: WireSegment) -> None:
        """
        Disconnects a port segment from its connected wire segment.

        This method removes the connection between the given port segment and the given wire segment.

        Args:
            p (PortSegment): The port segment to be disconnected.
            w (WireSegment): The wire segment to be disconnected.
        """
        # Disconnect Wire -> Port
        if p in w.port_segments:
            w.port_segments.remove(p)
            w.notify_listeners()
        # Disconnect Port -> Wire
        if p.raw_ws_path != w.raw_path:
            # To prevent discrepancies if the port segment was tied to a value (which does not notify the wire segment)
            return
        if p.parent_parent_name == self.name:
            return self._disconnect_module_port(p)
        return self._disconnect_instance_port(p.parent_parent_name, p)

    def _disconnect_module_port(self, p: PortSegment) -> None:
        """
        Disconnects a module port segment from its connected wire segment.

        This method sets the raw wire segment path of the given port segment to 'X', indicating no connection.

        Args:
            p (PortSegment): The port segment to be disconnected.
        """
        p.set_ws_path('')
        p.notify_listeners()

    def _disconnect_instance_port(self, instance_name: str, p: PortSegment) -> None:
        """
        Disconnects an instance port segment from its connected wire segment.

        This method modifies the connection of the given instance port segment to 'X', indicating no connection.

        Args:
            instance_name (str): The name of the instance.
            p (PortSegment): The port segment to be disconnected.
        """
        inst = self.get_instance(instance_name)
        inst.disconnect(p.parent_name, index=p.index)

    def _collect_port_edges(self, instance: Instance, port_name: str) -> Dict[int, WireSegment]:
        connections = instance.connections[port_name]
        return {index: self.get_from_path(connections[index]) for index in connections}

    @overload
    def get_edges(self, instance: Instance) -> Dict[str, Dict[int, WireSegment]]: ...
    @overload
    def get_edges(self, instance: str) -> Dict[str, Dict[int, WireSegment]]: ...

    def get_edges(self, instance: Union[str, Instance]) -> Dict[str, Dict[int, WireSegment]]:
        """
        Retrieves the edges connected to a given instance.

        This method returns a dictionary containing the names of ports as keys and dictionaries of wire segments as values.
        Each inner dictionary contains the index of a port segment as a key and the corresponding wire segment as a value.

        Args:
            instance (str): The name of the instance for which to retrieve edges.

        Returns:
            Dict[str, Dict[int, WireSegment]]: A dictionary containing the edges connected to the given instance.
        """
        edges: Dict[str, Dict[int, WireSegment]] = {}
        if isinstance(instance, str):
            inst = self.instances[instance]
        else:
            inst = instance
        for pname in inst.connections:
            edges[pname] = self._collect_port_edges(inst, pname)
        return edges

    def get_outgoing_edges(self, instance_name: str) -> Dict[str, Dict[int, WireSegment]]:
        edges = self.get_edges(instance_name)
        inst = self.instances[instance_name]
        return {pname: edges[pname] for pname in edges if inst.ports[pname].is_output}

    def get_incoming_edges(self, instance_name: str) -> Dict[str, Dict[int, WireSegment]]:
        edges = self.get_edges(instance_name)
        inst = self.instances[instance_name]
        return {pname: edges[pname] for pname in edges if inst.ports[pname].is_input}

    def _get_instance_from_ps_path(self, segment_path: PortSegmentPath) -> Optional[Union[Instance, Port]]:
        if segment_path.hierarchy_level >= 2:
            inst_idx = -3  # Index of the instance or module name to which this port segment belongs to
            inst_name = segment_path.get(inst_idx)
            port_idx = -2  # Index of the port name to which this port segment belongs to
            port_name = segment_path.get(port_idx)
            node = self.get_instance(inst_name) if inst_name in self.instances else self.get_port(port_name)
            return node
        LOG.error(f'Cannot get connected instance from port segment with path {segment_path.raw} in module {self.name}: Path seems invalid!')
        return None

    def _get_connected_nodes(self, ws_path: WireSegmentPath, ps_fc: Callable[[PortSegment], bool] = lambda ps: True) -> Set[PortSegment]:
        """Returns a set of port segment instances connected to the wire that is represented by the given wire segment path.

        Args:
            ws_path (WireSegmentPath): Path of the wire segment in question.
            ps_fc (Callable[[PortSegment], bool], optional): Filter function to filter port segments based on a given condition.
                Defaults to `lambda ps: True`, which does not filter any port segments and passes all connected port segments.
                The filter function (if given) must take a port segment instance and return a bool.

        Returns:
            Set[PortSegment]: A set of port segments that are connected to the given wire segment path
                and match the filter function (if given).
        """
        try:
            ws = self.get_from_path(ws_path)
            return {ps for ps in ws.port_segments if ps_fc(ps)}
        except PathResolutionError as e:
            raise PathResolutionError(f'Unable to find wire segment {ws_path.raw} in module {self.name}!') from e

    def get_wire_ports(self, ws_path: WireSegmentPath) -> Set[PortSegment]:
        """
        Retrieves the connected port segments of a given wire segment.

        Args:
            ws_path (WireSegmentPath): The path of the wire segment for which to retrieve connected port segments.

        Returns:
            Set[PortSegment]: A set of port segments connected to the wire segment associated with the given path.
        """
        return self._get_connected_nodes(ws_path)

    def get_driving_ports(self, ws_path: WireSegmentPath) -> Set[PortSegment]:
        """
        Retrieves the driving port segments of a given wire segment (i.e. the instances driving this wire segment).

        For each wire segment, the set of driving ports should contain exactly one entry,
        otherwise driver conflicts will arise.

        Args:
            ws_path (WireSegmentPath): The path of the wire segment for which to retrieve driving ports.

        Returns:
            Set[PortSegment]: A set of port segments driving the wire segment associated with the given path.
        """
        return self._get_connected_nodes(ws_path, ps_fc=lambda ps: ps.is_driver)

    def get_load_ports(self, ws_path: WireSegmentPath) -> Set[PortSegment]:
        """
        Retrieves the load port segments of a given wire segment (i.e. the instances driven by this wire segment).

        Args:
            ws_path (WireSegmentPath): The path of the wire segment for which to retrieve load ports.

        Returns:
            Set[PortSegment]: A set of port segments being load of the wire segment associated with the given path.
        """
        return self._get_connected_nodes(ws_path, ps_fc=lambda ps: ps.is_load)

    def get_neighbors(self, instance_name: str) -> Dict[str, Dict[int, List[PortSegment]]]:
        """
        Retrieves the neighboring port segments of a given instance.

        This method is needed to determine which port segments are connected to an instance.
        It returns a dictionary containing the names of ports as keys and dictionaries of lists of port segments
        (connected to this port through a wire) as values.
        Each inner dictionary contains the index of a port segment as a key and a list of corresponding port segments as a value.
        The corresponding port segments are port segments opposing the instance's port.
        If the instance port is an input port (i.e. a load), only the driver is considered its neighbor.
        If the instance port is an output port (.e. a signal driver), all loads are considered its neighbors.

        Args:
            instance_name (str): The name of the instance for which to retrieve neighbors.

        Returns:
            Dict[str, Dict[int, List[PortSegment]]]: A dictionary containing the neighboring port segments of the given instance.
        """
        neighbors: Dict[str, Dict[int, List[PortSegment]]] = {}
        if instance_name in self.instances:
            inst: Instance = self.get_instance(instance_name)
            edges = self.get_edges(instance_name)
            for pname in edges:
                neighbors[pname] = {}
                for idx in edges[pname]:
                    if inst.ports[pname].is_load:
                        neighbors[pname][idx] = edges[pname][idx].driver(warn_if_issue=True)
                    if inst.ports[pname].is_driver:
                        neighbors[pname][idx] = edges[pname][idx].loads(warn_if_issue=True)
        return neighbors

    def _get_neighboring_instances_directed(self, name: str, get_outgoing: bool) -> Dict[str, Dict[int, List[Union[Instance, Port[Module]]]]]:
        """
        Retrieves the neighboring instances of a given instance in a specific direction.

        This method returns a dictionary containing the names of ports as keys and dictionaries of lists of instances
        (connected to this port through a wire) as values.
        Each inner dictionary contains the index of a port segment as a key and a list of corresponding instances as a value.
        The corresponding instances are instances opposing the given instance's port.

        Args:
            name (str): The name of the instance for which to retrieve neighboring instances.
            get_outgoing (bool): Whether to retrieve outgoing or incoming neighbors.

        Returns:
            Dict[str, Dict[int, List[Union[Instance, Port]]]]: A dictionary containing the neighboring instances of the given instance.
        """
        insts: Dict[str, CustomDict[int, List[Union[Instance, Port[Module]]]]] = {}
        if name in self.instances:
            inst: Instance = self.get_instance(name)
            neighbors = self.get_neighbors(name)
            for portname in neighbors:
                if (inst.ports[portname].is_output and get_outgoing) or (inst.ports[portname].is_input and not get_outgoing):
                    insts[portname] = CustomDict()
                    for idx in neighbors[portname]:
                        port_segs = neighbors[portname][idx]
                        for seg in port_segs:
                            next_inst = self._get_instance_from_ps_path(seg.path)
                            insts[portname].append_or_create(idx, next_inst)
        return insts

    def get_succeeding_instances(self, instance_name: str) -> Dict[str, Dict[int, List[Union[Instance, Port[Module]]]]]:
        """
        Retrieves the succeeding instances of a given instance.

        This method returns the instances that are connected to the output ports of the given instance.
        It is needed for various graph-based analyses and algorithms, such as depth-first search or topological sorting.

        Args:
            instance_name (str): The name of the instance for which to retrieve succeeding instances.

        Returns:
            Dict[str, Dict[int, List[Union[Instance, Port]]]]: A dictionary containing the succeeding instances of the given instance.
        """
        return self._get_neighboring_instances_directed(instance_name, get_outgoing=True)

    def get_preceeding_instances(self, instance_name: str) -> Dict[str, Dict[int, List[Union[Instance, Port[Module]]]]]:
        """
        Retrieves the preceeding instances of a given instance.

        This method returns the instances that are connected to the input ports of the given instance.
        It is needed for various graph-based analyses and algorithms, such as depth-first search or topological sorting.

        Args:
            instance_name (str): The name of the instance for which to retrieve preceeding instances.

        Returns:
            Dict[str, Dict[int, List[Union[Instance, Port]]]]: A dictionary containing the preceeding instances of the given instance.
        """
        return self._get_neighboring_instances_directed(instance_name, get_outgoing=False)

    def optimize(self) -> bool:
        """
        Optimizes this module by removing unused wires and instances.

        More optimization algorithms may be implemented in the future.

        Returns:
            bool: True if any changes were made, False otherwise.
        """
        from netlist_carpentry.core.opt.loadless_wires import opt_loadless

        return opt_loadless(self)

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
            for p in i.ports.values():
                p.raw_path = p.path.replace(old_name, new_name).raw
                for _, s in p:
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

    def graph(self) -> nx.MultiDiGraph[str]:
        """
        The module graph represents the connectivity between instances and ports within a module.

        It is a directed multigraph where nodes represent instances or ports, and edges represent connections between them.
        This method returns the current state of the module's graph, rebuilding it if necessary when the module's internal state changes.

        Returns:
            A networkx MultiDiGraph object representing the connectivity of the module.
        """
        if self._prev_hash != hash(self):
            LOG.info('No valid cached graph found, building module graph...')
            self._prev_hash = hash(self)
            self._graph = self.build_graph()
        return self._graph

    def normalize_metadata(
        self,
        include_empty: bool = False,
        sort_by: Literal['path', 'category'] = 'path',
        filter: Callable[[str, NESTED_DICT], bool] = lambda cat, md: True,
    ) -> METADATA_DICT:
        md = super().normalize_metadata(include_empty=include_empty, sort_by=sort_by, filter=filter)
        elements = [i for i in self.instances.values()] + [p for p in self.ports.values()] + [w for w in self.wires.values()]
        for e in elements:
            md_sub = e.normalize_metadata(include_empty=include_empty, sort_by=sort_by, filter=filter)
            for cat, val in md_sub.items():
                if cat in md:
                    md[cat].update(val)
                else:
                    md[cat] = val
        return md

    def export_metadata(
        self,
        path: Union[str, Path],
        include_empty: bool = False,
        sort_by: Literal['path', 'category'] = 'path',
        filter: Callable[[str, NESTED_DICT], bool] = lambda cat, md: True,
    ) -> None:
        if isinstance(path, str):
            path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        md_dict = self.normalize_metadata(include_empty=include_empty, sort_by=sort_by, filter=filter)
        with open(path, 'w', encoding='utf-8') as f:
            # ensure_ascii=False: special characters are displayed correctly
            f.write(json.dumps(md_dict, indent=2, ensure_ascii=False))

    def __hash__(self) -> int:
        return hash(
            (
                self.path,
                tuple(hash(i) for i in self.instances.values()),
                tuple(hash(p) for p in self.ports.values()),
                tuple(hash(w) for w in self.wires.values()),
                tuple(hash(p) for p in self.parameters.values()),
            )
        )

    def __str__(self) -> str:
        return f'{self.__class__.__name__} "{self.name}"'

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.name})'
