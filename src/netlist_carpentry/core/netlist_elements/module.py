"""Module for handling circuit modules."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, List, Literal, Optional, Tuple, Type, TypeVar, Union, overload
from uuid import uuid4

from dash import Dash
from pydantic import BaseModel, NonNegativeInt, PositiveInt

from netlist_carpentry import LOG, Direction, Instance, Port, Wire
from netlist_carpentry.core.exceptions import (
    AlreadyConnectedError,
    IdentifierConflictError,
    InvalidDirectionError,
    MissingConnectionError,
    MultipleDriverError,
    ObjectLockedError,
    ObjectNotFoundError,
    SingleOwnershipError,
    StructureMismatchError,
    UnsupportedOperationError,
    WidthMismatchError,
)
from netlist_carpentry.core.netlist_elements.element_path import (
    T_PATH_TYPES,
    ElementPath,
    InstancePath,
    PortPath,
    PortSegmentPath,
    WirePath,
    WireSegmentPath,
)
from netlist_carpentry.core.netlist_elements.mixins.evaluation import EvaluationMixin
from netlist_carpentry.core.netlist_elements.mixins.graph_building import GraphBuildingMixin
from netlist_carpentry.core.netlist_elements.mixins.metadata import METADATA_DICT, NESTED_DICT
from netlist_carpentry.core.netlist_elements.mixins.module_bfs import ModuleBfsMixin
from netlist_carpentry.core.netlist_elements.mixins.module_dfs import ModuleDfsMixin
from netlist_carpentry.core.netlist_elements.netlist_element import NetlistElement
from netlist_carpentry.core.netlist_elements.port_segment import PortSegment
from netlist_carpentry.core.netlist_elements.wire_segment import CONST_MAP_VAL2OBJ, WireSegment
from netlist_carpentry.utils.cfg import CFG
from netlist_carpentry.utils.custom_dict import CustomDict
from netlist_carpentry.utils.custom_list import CustomList
from netlist_carpentry.utils.gate_lib_dataclasses import Parameters

T_NETLIST_ELEMENT = TypeVar('T_NETLIST_ELEMENT', bound=NetlistElement)
T_INSTANCE = TypeVar('T_INSTANCE', bound=Instance)
T_PORT = Union[Port['Module'], Port[Instance]]
ANY_SIGNAL_SOURCE = Union[PortSegmentPath, PortPath, PortSegment, T_PORT, WireSegmentPath, WirePath, WireSegment, Wire]
ANY_SIGNAL_TARGET = Union[PortSegmentPath, PortPath, PortSegment, T_PORT]
PARAMETERS = Union[Dict[str, object], Parameters]
if TYPE_CHECKING:
    from netlist_carpentry.routines.check.report import CheckReport


class Module(GraphBuildingMixin, EvaluationMixin, ModuleBfsMixin, ModuleDfsMixin, NetlistElement, BaseModel):
    _wire_gen_i: int = 0
    """Internal index for naming of generated wire names."""
    _inst_gen_i: int = 0
    """Internal index for naming of generated instance names."""

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, Module):
            return NotImplemented
        if not super().__eq__(value):
            return False
        return self.instances == value.instances and self.ports == value.ports and self.wires == value.wires

    def _raise_if_occupied(self, name: str) -> None:
        """Raises an IdentifierConflictError, if the given name is already used for a port, wire or instance.

        Args:
            name (str): The name to check, if an object with this name already exists.
        """
        if self.name_occupied(name):
            raise IdentifierConflictError(f'An object with name {name} exists already in module {self.name}!')

    def add_instance(self, instance: T_INSTANCE) -> T_INSTANCE:
        """
        Adds an instance to the module.

        Args:
            instance (Instance): The instance to be added.

        Returns:
            Instance: the instance that was added.
        """
        self._raise_if_occupied(instance.name)
        if instance.has_parent and instance.module is not self:
            raise SingleOwnershipError(f'Instance {self.raw_path} belongs to module {instance.parent.name}. Cannot add it to module {self.name}!')
        instance.module = self
        if self.has_circuit:
            self.circuit.update_instance(instance)
        return self.instances.add(instance.name, instance, locked=self.locked)  # type: ignore[return-value]

    @overload
    def create_instance(
        self, interface_definition: Type[T_INSTANCE], name: Optional[str] = None, params: Optional[PARAMETERS] = None
    ) -> T_INSTANCE: ...
    @overload
    def create_instance(self, interface_definition: Module, name: Optional[str] = None, params: Optional[PARAMETERS] = None) -> Instance: ...

    def create_instance(
        self, interface_definition: Union[Module, Type[T_INSTANCE]], name: Optional[str] = None, params: Optional[PARAMETERS] = None
    ) -> Instance:
        """
        Creates an instance within this module based on the given interface definition, instance name and parameters.

        If `interface_definition` is a module, this creates a submodule instance inside this module, based on the given
        instance name and module definition.
        The module is also added to the circuit if no module with this name already already exists.

        If `interface_definition` is a **class** (not an instance) that extends `netlist_carpentry.Instance` (e.g. a gate
        from the internal gate library), this creates a primitive gate instance inside this module.

        The instance type of the created instance is either the name of the provided module or the type of the provided instance class.
        The instance is thus linked to either the module definition or the type of the given instance by its own instance type.

        Args:
            interface_definition (Union[Module, Instance]): The module whose interface is to be copied to the new instance.
                Alternatively, the primitive instance **class**, whose interface is to be copied to the new instance.
            name (Optional[str], optional): The target name of the instance to be created. Defaults to None,
                in which case a generic name is created and used.
            params (Dict[str, object]): A dictionary containing parameters for the instance to be created

        Returns:
            Instance: The instance that was created and added.
        """
        if params is None:
            params = Parameters()
        if name is None:
            name = self._get_generic_inst_name(interface_definition)
        if isinstance(interface_definition, Module):
            inst = Instance(name=name, instance_type=interface_definition.name, module=self)
            inst.parameters = params  # type: ignore
            for pname, p in interface_definition.ports.items():
                inst.connect(pname, ws_path=None, direction=p.direction, width=p.width)
            if self.has_circuit and interface_definition.name not in self.circuit:
                if interface_definition.has_circuit and self.circuit != interface_definition.circuit:
                    interface_definition = self.circuit.copy_module(interface_definition, interface_definition.name)
                else:
                    self.circuit.add_module(interface_definition)
        else:
            inst = interface_definition(name=name, module=self, parameters=dict(params))  # type: ignore
        return inst

    def _get_generic_inst_name(self, module_or_inst_cls: Union[Module, Type[Instance]]) -> str:
        """Returns a generic name for a given module or instance class, which is used for instantiating said object.

        The generic name is based on the type abbreviation, which is either the module name (if it is a module),
        or the class name (if it is an instance).
        A generic name for a module `Foo` would be `_Foo_0_`, which will be the generic name for an instance of module `Foo`,
        if no name is specified when calling `Module.create_instance()`.
        Analogously, if an instance class is passed, e.g. the class `AndGate` from the gate library, the generic name will be
        `_AndGate_0_` (or `_AndGate_1_` if the previous already exists, and so on).
        """
        type_abbrev = module_or_inst_cls.name if isinstance(module_or_inst_cls, Module) else module_or_inst_cls.__name__
        while f'_{type_abbrev}_{self._inst_gen_i}_' in self.instances:
            self._inst_gen_i += 1
        return f'_{type_abbrev}_{self._inst_gen_i}_'

    def copy_instance(self, instance: Union[str, Instance], new_name: str, keep_inputs: bool = False) -> Instance:
        """
        Copies the given instance within this module.

        Takes either an Instance object or a string (which must be a name of an already existing instance within this module.
        The instance is then copied and is completely identical to the given instance (or the instance with the given name,
        if a string is passed instead), except for the given `name`.
        Also, all ports of the new instance are initially unconnected.

        Args:
            instance (Union[str, Instance]): The instance to copy. If a string is provided, it must be the name of an instance
                that exists within this module.
            new_name (str): The new name of the copied instance. Must be a name that is not already given to another instance.
            keep_inputs (bool, optional): Whether to disconnect the input ports of the instance (so it is entirely unconnected).
                Defaults to True.
        """
        if isinstance(instance, str):
            instance = self.instances[instance]
        new_instance = instance.copy_object(new_name)
        if self is not new_instance.module:  # Added to another module
            new_instance.parent.remove_instance(new_instance)
            self.add_instance(new_instance)
        prev_module_name = new_instance.path.parts[0]
        for p in new_instance.ports.values():
            p.module_or_instance = new_instance
            for _, ps in p:
                ps.set_ws_path('')
        if keep_inputs:
            for p in new_instance.input_ports:
                for idx, ps in p:
                    instance.ports[p.name][idx].set_ws_path(instance.ports[p.name][idx].ws_path.replace(prev_module_name, self.name))
                    self.connect(instance.ports[p.name][idx].ws_path, ps)
        return new_instance

    def refine_instance(self, old_instance: Union[str, Instance], new_type_definition: Union[Module, Type[Instance]]) -> None:
        """
        **Replaces an existing instance** with a new one of a different type.

        This method swaps the definition of an instance while attempting to preserve
        its original name and port connections. It first verifies that the new
        module definition contains all the necessary ports used by the old instance.

        **The original object is removed and replaced with a new object!**
        The old reference won't point to a valid instance anymore.

        Args:
            old_instance (Union[str, Instance]): The instance to be replaced. Can be either the
                Instance object itself or its name (as string).
            new_type_definition (Module): The Module definition that the new instance
                should be based on.

        Raises:
            ObjectNotFoundError: If the specified `old_instance` does not exist
                within this module.
            StructureMismatchError: If the new instance is missing ports that
                were connected in the old instance.
        """
        if isinstance(old_instance, Instance):
            old_instance = old_instance.name
        if old_instance not in self.instances:
            raise ObjectNotFoundError(f'Cannot replace instance {old_instance}, since no such instance exists in module {self.name}!')
        old_instance = self.instances[old_instance]
        new_instance = self.create_instance(new_type_definition, old_instance.name + uuid4().hex, params=old_instance.parameters.as_dict())
        self._substitute_check_ports(old_instance, new_instance)
        connections = old_instance.connections
        self.remove_instance(old_instance)
        new_instance.set_name(old_instance.name)
        self._substitute_connect(new_instance, connections)

    def substitute_instance(self, old_instance: Union[str, Instance], new_instance: Instance) -> None:
        """Replaces an existing instance in the module with a new instance.

        This method validates the existence of the instance to be replaced
        and ensures the new instance's name does not cause a conflict within the module.

        Args:
            old_instance (Union[str, Instance]): The instance to be replaced. Can be either the
                instance name (str) or the Instance object itself.
            new_instance (Instance): The new instance (submodule or gate) to be inserted.

        Raises:
            ObjectNotFoundError: If `old_instance` does not exist in the module.
            IdentifierConflictError: If `new_instance.name` is already taken by
                another instance in the module.
            StructureMismatchError: If the new instance is missing ports that
                were connected in the old instance.
            WidthMismatchError: If a port name matches but the bit-width differs
                between the old and new instance.
        """
        if isinstance(old_instance, Instance):
            old_instance = old_instance.name
        if old_instance not in self.instances:
            raise ObjectNotFoundError(f'Cannot replace instance {old_instance}, since no such instance exists in module {self.name}!')
        if new_instance.name in self.instances:
            raise IdentifierConflictError(
                f'Error whilst replacing instance {old_instance} with {new_instance.raw_path}: '
                + f'An instance with name {new_instance.name} already exists in module {self.name}!'
            )
        self._substitute_instance(self.instances[old_instance], new_instance)

    def _substitute_instance(self, old_instance: Instance, new_instance: Instance) -> None:
        """Performs the internal logic of swapping instances and reconnecting nets.

        This method verifies port compatibility (presence and width), removes the
        old instance, adds the new instance, and maps the existing net connections
        from the old ports to the new ports.

        Args:
            old_instance (Instance): The Instance object to be removed.
            new_instance (Instance): The Instance object to be added.

        Raises:
            StructureMismatchError: If the new instance is missing ports that
                were connected in the old instance (to prevent dangling nets).
            WidthMismatchError: If a port exists in both instances but has
                different bit-widths.
        """
        self._substitute_check_ports(old_instance, new_instance)
        connections = old_instance.connections
        self.remove_instance(old_instance)
        self.add_instance(new_instance)
        self._substitute_connect(new_instance, connections)

    def _substitute_check_ports(self, old_instance: Instance, new_instance: Instance) -> None:
        missing_ports = {p.name for p in old_instance.ports.values() if not p.is_unconnected and p.name not in new_instance.ports}
        if missing_ports:
            raise StructureMismatchError(
                f'Unable to replace {old_instance.raw_path}: New instance {new_instance.raw_path} is missing these ports: {", ".join(missing_ports)}'
            )
        for pname, p in old_instance.ports.items():
            if pname in new_instance.ports and p.width > new_instance.ports[pname].width:
                raise WidthMismatchError(
                    f'Port {pname} is {p.width} bit wide in {old_instance.raw_path}, but {new_instance.ports[pname].width} bit wide in {new_instance.raw_path}'
                )

    def _substitute_connect(self, new_instance: Instance, connections: Dict[str, Dict[int, WireSegmentPath]]) -> None:
        for pname in list(new_instance.ports.keys()):
            if pname in connections:
                p = new_instance.ports[pname]
                for idx, ps in p:
                    if idx in connections[pname]:
                        self.connect(connections[pname][idx], ps)

    def remove_instance(self, instance: Union[str, Instance]) -> None:
        """
        Removes an instance from the module.

        Args:
            instance (Union[str, Instance}): The name of the instance to be removed, or the Instance object itself.
        """
        instance_name = instance.name if isinstance(instance, Instance) else instance
        if instance_name in self.instances:
            inst = self.instances[instance_name]
            if self.has_circuit and inst.path in self.circuit.instances[inst.instance_type]:
                self.circuit.instances[inst.instance_type].remove(inst.path)
                if not self.circuit.instances[inst.instance_type]:
                    self.circuit.instances.pop(inst.instance_type)
            for p in inst.ports.values():
                for _, ps in p:
                    self.disconnect(ps)
            inst.module = None
        self.instances.remove(instance_name, locked=self.locked)

    def get_instance(self, name: str) -> Optional[Instance]:
        """
        Retrieves an instance by its name.

        Guarded alternative to Module.instances[name], with fallback to return None if not found.

        Args:
            name (str): The name of the instance to be retrieved.

        Returns:
            Optional[Instance]: The instance with the specified name if found, otherwise None.
        """
        return self.instances.get(name, None)

    def get_instances(
        self, *, name: Optional[str] = None, type: Optional[str] = None, fuzzy: bool = False, recursive: bool = False
    ) -> List[Instance]:
        """
        Retrieves a list of instances based on the given criteria.

        Args:
            name (Optional[str], optional): The name of the instance to be searched for. Defaults to None.
            type (Optional[str], optional): The type of the instance to be searched for. Defaults to None.
            fuzzy (bool, optional): Whether to perform a fuzzy search or not. Defaults to False.
                Fuzzy search means, the given string is used case-insensitive and substrings are accepted.
                If a name "inst" is given, this method will return instances named "INST", "someInst",
                i.e. all instances whose name contains "inst", regardless of case and pre- or suffixes.
            recursive (bool, optional): Whether to scan submodules as well. Defaults to False.

        Returns:
            List[Instance]: A list of instances matching the specified criteria.
        """
        nr_set_args = sum([name is not None, type is not None])
        if nr_set_args > 1:
            LOG.warn(f'Only one argument of "name" or "type" must be set to get instances, but {nr_set_args} arguments were set!')
            return []
        sub_insts: List[Instance] = []
        if recursive:
            for inst in self.submodules:
                sub_insts.extend(inst.module_definition.get_instances(name=name, type=type, fuzzy=fuzzy, recursive=True))
        if name is not None:
            return [self.instances[i_name] for i_name in self.instances if (name in i_name and fuzzy) or (name == i_name)] + sub_insts
        if type is not None:
            inst_list = CustomList(
                [self.instances_by_types[i_type] for i_type in self.instances_by_types if (type in i_type and fuzzy) or (type == i_type)]
            )
            return inst_list.flatten() + sub_insts
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
        if port.name in self.instances or port.name in self.ports:  # Ignore wires, as ports normally have a wire with the same name
            raise IdentifierConflictError(f'An object with name {port.name} exists already in module {self.name}!')
        if port.module_or_instance is not None and port.module_or_instance is not self:
            raise SingleOwnershipError(f'Port {self.raw_path} belongs to module {port.module.name}. Cannot add it to module {self.name}!')
        port.module_or_instance = self
        return self.ports.add(port.name, port, locked=self.locked)

    def _get_direction(self, direction: Union[str, Direction]) -> Direction:
        if isinstance(direction, str):
            if Direction.get(direction) == Direction.UNKNOWN:
                LOG.warn(f"Direction '{direction}' is unknown. Setting direction of port to Direction.UNKNOWN.")
            return Direction.get(direction)
        return direction

    def create_port(
        self,
        name: str,
        direction: Union[str, Direction] = Direction.UNKNOWN,
        width: PositiveInt = 1,
        offset: NonNegativeInt = 0,
        is_locked: bool = False,
    ) -> Port[Module]:
        """
        Creates a new port within the module and connects it to the specified wire segments.

        Returns the port object, if it was created successfully (i.e. no port with the same name exists already), or None otherwise.
        If the port was not created (because it already exists), the provided wire segment paths are ignored.

        Args:
            name (str): The name of the port to be created.
            direction (Union[str, Direction], optional): The direction of the port. May also be the name of the
                direction as a string, e.g. "input", "InOut" or "OUT". Defaults to Direction.UNKNOWN.
            width (PositiveInt, optional): The width of the port. Defaults to 1, which means the port is 1 bit wide.
            offset (NonNegativeInt, optional): The index offset for port slices. Defaults to 0, which means the port indexing starts at 0.
            is_locked (bool, optional): Whether the port should be unchangeable after creation or not. Defaults to False.

        Returns:
            Optional[Port]: The port if the port was successfully created and added, None otherwise (if a port with this name already exists).
        """
        p = Port(name=name, direction=self._get_direction(direction), module_or_instance=self)
        p.create_port_segments(width, offset)
        p.change_mutability(is_now_locked=is_locked)
        LOG.debug(f'Created port {p.raw_path}, {width} bit wide.')
        return p

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
            self.ports[port_name].module_or_instance = None
        self.ports.remove(port_name, locked=self.locked)

    def get_port(self, name: str) -> Optional[Port[Module]]:
        """
        Retrieves a port by its name.

        Guarded alternative to Module.port[name], with fallback to return None if not found.

        Args:
            name (str): The name of the port to be retrieved.

        Returns:
            Port: The port with the specified name if found, otherwise None.
        """
        return self.ports.get(name, None)

    def get_ports(self, *, name: Optional[str] = None, direction: Optional[Direction] = None, fuzzy: bool = False) -> List[Port[Module]]:
        """
        Retrieves a list of ports based on the given criteria.

        Args:
            name (Optional[str], optional): The name of the port to be searched for. Defaults to None.
            direction (Direction, optional): The direction of the port to be searched for. Defaults to None.
            fuzzy (bool, optional): Whether to perform a fuzzy search or not. Defaults to False.
                Fuzzy search means, the given string is used case-insensitive and substrings are accepted.
                If a name "port" is given, this method will return ports named "PORT", "somePort",
                i.e. all ports whose name contains "port", regardless of case and pre- or suffixes.

        Returns:
            List[Port]: A list of ports matching the specified criteria.
        """
        nr_set_args = sum([name is not None, direction is not None])
        if nr_set_args > 1:
            LOG.warn(f'Only one argument of "name" or "direction" must be set to get ports, but {nr_set_args} arguments were set!')
            return []
        if name is not None:
            return [self.ports[p_name] for p_name in self.ports if (name in p_name and fuzzy) or (name == p_name)]
        if direction is not None:
            return [
                self.ports[p_name]
                for p_name in self.ports
                if (fuzzy and self._fuzzy_direction(direction, self.ports[p_name].direction)) or (self.ports[p_name].direction == direction)
            ]
        LOG.warn(f'At least "name" or "direction" must be set to get ports, but name was "{name}" and direction was "{direction}"!')
        return []

    def _fuzzy_direction(self, target_dir: Direction, found_dir: Direction) -> bool:
        """
        Checks if a port direction matches the target direction in a fuzzy manner.

        Args:
            target_dir (Direction): The target direction to be matched.
            found_dir (Direction): The direction of the port being checked.

        Returns:
            bool: True if the port direction matches the target direction, False otherwise.
        """
        return target_dir == found_dir or found_dir == Direction.IN_OUT

    def add_wire(self, wire: Wire) -> Wire:
        """
        Adds a wire to the module.

        Args:
            wire (Wire): The wire to be added.

        Returns:
            Wire: The wire that was added.
        """
        if wire.name in self.instances or wire.name in self.wires:  # Ignore wires, as wires may have a port with the same name
            raise IdentifierConflictError(f'An object with name {wire.name} exists already in module {self.name}!')
        if wire.has_parent and wire.module is not self:
            raise SingleOwnershipError(f'Wire {self.raw_path} belongs to module {wire.parent.name}. Cannot add it to module {self.name}!')
        wire.module = self
        return self.wires.add(wire.name, wire, locked=self.locked)

    def create_wire(self, name: Optional[str] = None, width: PositiveInt = 1, is_locked: bool = False, offset: NonNegativeInt = 0) -> Wire:
        """
        Creates a new wire within the module.

        Returns the wire object, if it was created successfully (i.e. no wire with the same name exists already), or None otherwise.

        Args:
            name (Optional[str]): The name of the wire to be created. Defaults to None, in which case a generic wire is created.
                In this case, the name of the wire is `_ncgen_{index}_`.
            width (PositiveInt, optional): The number of segments in the wire. Defaults to 1.
            is_locked (bool, optional): Whether the wire should be unchangeable after creation or not. Defaults to False.
            offset (NonNegativeInt, optional): The offset for the segment indices. Defaults to 0.

        Returns:
            Optional[Wire]: The wire if the wire was successfully created and added, None otherwise (if a wire with this name already exists).
        """
        if not name:
            return self._create_generic_wire(width, is_locked, offset)
        w = Wire(name=name, module=self)
        w.create_wire_segments(width, offset)
        return w.change_mutability(is_now_locked=is_locked)

    def _create_generic_wire(self, width: PositiveInt = 1, is_locked: bool = False, offset: NonNegativeInt = 0) -> Wire:
        """
        Creates a new wire with a generic name within the module and returns the wire object.

        Args:
            width (PositiveInt, optional): The number of segments in the wire. Defaults to 1.
            is_locked (bool, optional): Whether the wire should be unchangeable after creation or not. Defaults to False.
            offset (NonNegativeInt, optional): The offset for the segment indices. Defaults to 0.

        Returns:
            Wire: The created wire.
        """
        while self.name_occupied(f'_ncgen_{self._wire_gen_i}_'):
            self._wire_gen_i += 1
        gen_name = f'_ncgen_{self._wire_gen_i}_'
        return self.create_wire(gen_name, width=width, is_locked=is_locked, offset=offset)

    def remove_wire(self, wire: Union[str, Wire]) -> None:
        """
        Removes a wire from the module.

        Args:
            wire (Union[str, Wire]): The name of the wire to be removed, or the Wire object itself.
        """
        wire_name = wire.name if isinstance(wire, Wire) else wire
        if wire_name in self.wires:
            for plist in self.wires[wire_name].connected_port_segments.values():
                for p in plist.copy():
                    self.disconnect(p.path)
            self.wires[wire_name].module = None
        self.wires.remove(wire_name, locked=self.locked)

    def get_wire(self, name: str) -> Optional[Wire]:
        """
        Retrieves a wire by its name.

        Guarded alternative to Module.wires[name], with fallback to return None if not found.

        Args:
            name (str): The name of the wire to be retrieved.

        Returns:
            Wire: The wire with the specified name if found, otherwise None.
        """
        return self.wires.get(name, None)

    def get_wires(self, *, name: Optional[str] = None, fuzzy: bool = False) -> List[Wire]:
        """
        Retrieves a list of wires based on the given criteria.

        Args:
            name (Optional[str], optional): The name of the wire to be searched for. Defaults to None.
            fuzzy (bool, optional): Whether to perform a fuzzy search or not. Defaults to False.
                Fuzzy search means, the given string is used case-insensitive and substrings are accepted.
                If a name "wire" is given, this method will return wires named "WIRE", "someWire",
                i.e. all wires whose name contains "wire", regardless of case and pre- or suffixes.

        Returns:
            List[Wire]: A list of wires matching the specified criteria.
        """
        if name is not None:
            return [self.wires[w_name] for w_name in self.wires if (name in w_name and fuzzy) or (name == w_name)]
        LOG.warn(f'A "name" must be set to get wires, but name was "{name}"!')
        return []

    def name_occupied(self, name: str) -> bool:
        """Checks if a given identifier is already in use within the module.

        This method verifies if the name conflicts with any existing instances,
        ports, or wires defined in the module's namespace.

        Args:
            name: The string identifier to check for existence.

        Returns:
            True if the name is already used by an instance, port, or wire;
            False otherwise.
        """
        return name in self.instances or name in self.ports or name in self.wires

    def connect(self, source: ANY_SIGNAL_SOURCE, target: ANY_SIGNAL_TARGET, new_wire_name: Optional[str] = None) -> None:
        """Connects the target (a portlike object) to the source (a portlike or a wirelike object).

        This method establishes a connection between *source* and *target*, where *source* is the origin of the signal.
        The following connection patterns are supported:

        =========================  ===================================  ==================================
        Source                     Target                               Behavior
        =========================  ===================================  ==================================
        Wire / WireSegment         Port / PortSegment                   Connect target to the given wire
        Port (unconnected)         Port (unconnected)                   Create a new wire, connect both
        Port (connected)           Port (unconnected)                   Connect target to source's wire
        PortSegment                PortSegment                          Connect via source's wire or new wire
        =========================  ===================================  ==================================

        **Requirements:**

        * The **target** must be unconnected (no existing wire attachment).
        * Source and target must be compatible: either both are segments, or both have matching widths.
        * Path objects (``PortPath``, ``WirePath``, ``PortSegmentPath``, ``WireSegmentPath``) are accepted for all arguments.

        Args:
            source: The signal source. May be a ``Wire``, ``WireSegment``, ``Port``, ``PortSegment``, or any
                corresponding path type.
            target: The signal target (must be a port-like object). May be a ``Port``, ``PortSegment``, or any
                corresponding path type.
            new_wire_name: Optional name for a newly created wire (used when source and target are both
                unconnected ports/segments). If ``None``, a generic name is generated.

        Raises:
            AlreadyConnectedError: If the target port/segment is already connected to a wire.
            InvalidDirectionError: If the target is a driver port (both source and target cannot drive).
            WidthMismatchError: If source and target have incompatible widths.
            UnsupportedOperationError: If mixing segment-level and non-segment-level objects.
        """
        # Resolve any path objects to their underlying NetlistElement
        source_obj = self._get_from_path_or_object(source)
        target_obj = self._get_from_path_or_object(target)

        # Validate: target must be unconnected
        if not target_obj.is_unconnected:
            raise AlreadyConnectedError(f'{target_obj.type.value} {target_obj.raw_path} must be unconnected before attempting to connect it!')

        # Dispatch based on source/target types
        if isinstance(source_obj, (WireSegment, Wire)):
            self._connect_wire_to_port(source_obj, target_obj)
        elif isinstance(source_obj, Port) and isinstance(target_obj, Port):
            self._connect_ports_full(source_obj, target_obj, new_wire_name=new_wire_name)
        elif source_obj.type.is_segment != target_obj.type.is_segment:
            raise UnsupportedOperationError(
                f'Cannot connect {source_obj.type.value} to {target_obj.type.value}: Can only connect segments to segments!'
            )
        else:
            self._connect_segments(source_obj, target_obj, new_wire_name)

    def _connect_segments(
        self,
        source_seg: Union[PortSegment, WireSegment],
        target_seg: Union[PortSegment, WireSegment],
        new_wire_name: Optional[str] = None,
    ) -> None:
        """Connect two segments via a wire segment.

        If the source is an unconnected port segment, a new wire is created.
        Otherwise the source's existing wire is reused.
        Both segments are connected directly to the wire segment, bypassing
        the full dispatch chain for efficiency.
        """
        # Determine the wire segment: new if source port is unconnected, else reuse
        if isinstance(source_seg, PortSegment) and source_seg.is_unconnected:
            wire_seg = self.create_wire(new_wire_name)[0]
        else:
            wire_seg = source_seg.ws  # type: ignore[union-attr]

        # Connect both segments directly to the wire segment
        self._connect_to_wire_segment(source_seg, wire_seg)
        self._connect_to_wire_segment(target_seg, wire_seg)

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
        """Connect two full ports bit-by-bit.

        Each bit of the *driver* port is connected to the corresponding bit of the *load* port.
        If the driver port is unconnected, a new wire of matching width is created.
        If the driver port is already connected to a wire, that wire is reused.
        All connections are made directly via ``_connect_to_wire_segment`` to avoid
        the overhead of re-dispatching through ``connect()``.

        Args:
            driver: The driving port (must not itself be a driver).
            load: The loaded port (will receive signals from *driver*).
            new_wire_name: Optional name for a newly created wire.

        Raises:
            InvalidDirectionError: If the target port is also a driver.
            WidthMismatchError: If the two ports have different widths.
        """
        if load.is_driver:
            raise InvalidDirectionError(f'Received a signal driving port {load.raw_path}, but expected a load!')

        if driver.width != load.width:
            raise WidthMismatchError(
                f'Connection failed: Port {driver.raw_path} is {driver.width} bit wide '
                f'and port {load.raw_path} is {load.width} bit wide. '
                'Consider explicit bitwise connection of each port_segment:port_segment instead of port:port '
                'in such cases. Example:\n\tconnect(port.segment[0], port.segment[3])\n'
                '\tconnect(port.segment[1], port.segment[4])'
            )

        # Create a new wire only if the driver is unconnected
        wire = self.create_wire(new_wire_name, width=driver.width) if driver.is_unconnected_partly else None

        load_offset = load.offset or 0
        for idx, dr_seg in driver:
            # Pick the wire segment: reuse existing or use newly created
            ws = dr_seg.ws if dr_seg.is_connected else wire[idx]

            # Connect driver segment (if unconnected) and load segment to the same wire
            if dr_seg.is_unconnected:
                self._connect_to_wire_segment(dr_seg, ws)
            self._connect_to_wire_segment(load[idx + load_offset], ws)

    def _connect_wire_to_port(
        self,
        wire_like: Union[WireSegment, Wire],
        port_like: Union[PortSegment, T_PORT],
    ) -> None:
        """Connect a wire (or wire segment) to a port (or port segment).

        Handles full wire→port (bit-by-bit via ``_connect_to_wire_segment``),
        or normalizes to segment-level and connects directly.
        """
        # Full wire → full port: connect bit-by-bit directly
        if isinstance(wire_like, Wire) and isinstance(port_like, Port):
            if wire_like.width != port_like.width:
                raise WidthMismatchError(
                    f'Connection failed: Wire {wire_like.raw_path} is {wire_like.width} bit wide '
                    f'and port {port_like.raw_path} is {port_like.width} bit wide. '
                    'Consider explicit bitwise connection of each wire_segment:port_segment instead of wire:port '
                    'in such cases. Example:\n\tconnect(wire.segment[0], port.segment[3])\n'
                    '\tconnect(wire.segment[1], port.segment[4])'
                )
            for idx in wire_like.segments:
                self._connect_to_wire_segment(port_like[idx], wire_like[idx])
            return

        # Normalize to segment-level objects
        wire_seg = wire_like[wire_like.offset or 0] if isinstance(wire_like, Wire) else wire_like
        port_seg = port_like[port_like.offset or 0] if isinstance(port_like, Port) else port_like

        # Check lock status before proceeding
        if port_seg.locked or (wire_seg.locked and not wire_seg.is_constant) or self.locked:
            LOG.error(
                f'Unable to connect port segment at {port_seg.raw_path} to wire segment {wire_seg.raw_path} in module {self.name}: locked object!'
            )
            return

        self._connect_to_wire_segment(port_seg, wire_seg)

    def _connect_to_wire_segment(self, p: PortSegment, w: WireSegment) -> None:
        """
        Connects a port segment and a wire segment.

        This method connects the given port segment to the given wire segment.

        Args:
            p (PortSegment): The port segment to be connected.
            w (WireSegment): The wire segment to be connected.
        """
        # Connect Wire -> Port
        if not w.is_constant:
            w.port_segments.add(p)
        # Connect Port -> Wire
        if p.parent.module.name == self.name:
            # Connect a module port segment to a wire segment
            p.set_ws_path(w.raw_path)
        else:
            # Connect an instance port segment to a wire segment
            inst = p.parent.module.instances[p.grandparent.name]
            inst.modify_connection(p.parent.name, w.path, index=p.index)

    def disconnect(self, port_like: Union[PortSegmentPath, PortPath, PortSegment, T_PORT]) -> None:
        """
        Disconnects a port segment from its connected wire segment.

        Args:
            port_like (Union[PortSegmentPath, PortSegment]): The path of the port segment to be disconnected, or the PortSegment itself.
                Also accepts ports, aqd will then disconnect the complete port.
        """
        if isinstance(port_like, Port):
            return self._disconnect_port(port_like)
        elif isinstance(port_like, PortPath):
            return self.disconnect(self.get_from_path(port_like))
        elif isinstance(port_like, PortSegmentPath):
            p = self.get_from_path(port_like)
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
        # Disconnect Port -> Wire
        if p.raw_ws_path != w.raw_path:
            # To prevent discrepancies if the port segment was tied to a value (which does not notify the wire segment)
            return
        if p.grandparent.name == self.name:
            p.set_ws_path('')
        else:
            inst = self.instances[p.grandparent.name]
            inst.disconnect(p.parent.name, index=p.index)

    def reconnect(self, source: Union[PortPath, T_PORT], target: Union[PortPath, T_PORT]) -> None:
        """
        Moves (or reconnects) all existing wire connections from a source port to a target port.

        This method acts as a wrapper that accepts either port objects (Port[Instance] or Port[Module]) or
        hierarchical paths (PortPath). It resolves any paths into their respective
        port objects before performing the reconnection.

        In this process, the wire(s) connected to the source port are removed from the source port and connected
        (in the same order) to the target port.
        The target port must be unconnected!

        Args:
            source (Union[PortPath, T_PORT]): The port (or path to the port) currently holding the connections.
            target (Union[PortPath, T_PORT]): The destination port (or path) where the connections should be moved.

        Raises:
            MissingConnectionError: If the source port has no wires connected to it.
            AlreadyConnectedError: If at least one segment of the target port is already connect to a wire.
            WidthMismatchError: If the given ports have different widths.
        """
        if isinstance(source, PortPath):
            source = self.get_from_path(source)
        if isinstance(target, PortPath):
            target = self.get_from_path(target)
        self._reconnect(source, target)

    def _reconnect(self, source: T_PORT, target: T_PORT) -> None:
        """
        Internal implementation for transferring wire segments between port objects.

        This method disconnects all wire segments from the source port and
        attaches them to the corresponding indices of the target port.

        Args:
            source: The port object to disconnect wires from.
            target: The port object to connect the wires to.

        Raises:
            MissingConnectionError: If the source port has no wires connected to it.
            AlreadyConnectedError: If at least one segment of the target port is already connect to a wire.
            WidthMismatchError: If the given ports have different widths.
        """
        if source.width != target.width:
            raise WidthMismatchError(f'Cannot reconnect {source.raw_path} to {target.raw_path}: Ports have different widths!')
        if source.is_unconnected:
            raise MissingConnectionError(f'Cannot reconnect {source.raw_path} to {target.raw_path}: Source port has no connection!')
        orig_con = source.connected_wire_segments.copy()
        self.disconnect(source)
        for idx, ws_path in orig_con.items():
            self.connect(ws_path, target[idx])

    def _collect_port_edges(self, instance: Instance, port_name: str) -> Dict[int, WireSegment]:
        connections = instance.connections[port_name]
        return {index: self.get_from_path(connections[index]) for index in connections}

    def update_module_instances(self) -> None:
        """Updates all related entries in the `instances` dictionary of this module's superordinate circuit.

        This method iterates through all entries of the parent circuit's `instances` dictionary that refer to instances
        of this module (i.e. it searches for all instances of this module within the circuit). For each found instance
        of this module, it updates the instance interface. If new ports were added to this module, each module instance
        will receive the new port (but without any connections to it). If a port was deleted from this module, each module
        instance will also lose the corresponding port, which gets disconnected from any previously connected wire.
        """
        for inst_path in self.circuit.instances[self.name]:
            inst = self.circuit.get_from_path(inst_path)
            for pname, p in self.ports.items():
                if pname not in inst.ports:
                    offset = p.offset if p.offset is not None else 0
                    inst.connect(pname, None, direction=p.direction, index=offset, width=p.width)
            mark_del = set()
            for pname in inst.ports:
                if pname not in self.ports:
                    inst.disconnect(pname)
                    mark_del.add(pname)
            for pname in mark_del:
                inst.ports.pop(pname)

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
        """Retrieves all connections associated with the output ports of a specific instance.

        This method filters all edges of the given instance to return only those
        connected to its output ports.

        Args:
            instance_name (str): The name of the instance (submodule or gate) to query.

        Returns:
            A dictionary mapping output port names to their connections. The structure is:
                {
                    port_name (str): {
                        bit_index (int): wire_segment (WireSegment)
                    }
                }

        Raises:
            KeyError: If `instance_name` does not exist in the module's instances.
        """
        edges = self.get_edges(instance_name)
        inst = self.instances[instance_name]
        return {pname: edges[pname] for pname in edges if inst.ports[pname].is_output}

    def get_incoming_edges(self, instance_name: str) -> Dict[str, Dict[int, WireSegment]]:
        """Retrieves all connections associated with the input ports of a specific instance.

        This method filters all edges of the given instance to return only those
        connected to its input ports.

        Args:
            instance_name (str): The name of the instance (submodule or gate) to query.

        Returns:
            A dictionary mapping input port names to their connections. The structure is:
            {
                port_name (str): {
                    bit_index (int): wire_segment (WireSegment)
                }
            }

        Raises:
            KeyError: If `instance_name` does not exist in the module's instances.
        """
        edges = self.get_edges(instance_name)
        inst = self.instances[instance_name]
        return {pname: edges[pname] for pname in edges if inst.ports[pname].is_input}

    def _get_instance_from_ps_path(self, segment_path: PortSegmentPath) -> Optional[Union[Instance, Port[Module]]]:
        if segment_path.hierarchy_level >= 2:
            inst_idx = -3  # Index of the instance or module name to which this port segment belongs to
            inst_name = segment_path.get(inst_idx)
            port_idx = -2  # Index of the port name to which this port segment belongs to
            port_name = segment_path.get(port_idx)
            node = self.get_instance(inst_name) if inst_name in self.instances else self.get_port(port_name)
            return node
        LOG.error(f'Cannot get connected instance from port segment with path {segment_path.raw} in module {self.name}: Path seems invalid!')
        return None

    def get_wire_ports(self, ws_path: WireSegmentPath) -> List[PortSegment]:
        """
        Retrieves the connected port segments of a given wire segment.

        Args:
            ws_path (WireSegmentPath): The path of the wire segment for which to retrieve connected port segments.

        Returns:
            List[PortSegment]: A list of port segments connected to the wire segment associated with the given path.
        """
        return self._get_connected_nodes(ws_path)

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
            inst = self.instances[instance_name]
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
        G = self.graph()
        neighbors = G.out_edges(name, keys=True, data=True) if get_outgoing else G.in_edges(name, keys=True, data=True)

        insts: Dict[str, CustomDict[int, List[Union[Instance, Port[Module]]]]] = {}
        for n, v, key, data in neighbors:
            neighbor_node = v if get_outgoing else n
            neighbor = self.instances[neighbor_node] if neighbor_node in self.instances else self.ports[neighbor_node]
            node_port_name: str = key.split(CFG.id_internal)[0 if get_outgoing else 1]
            node_index = data['dr_seg'] if get_outgoing else data['ld_seg']
            if node_port_name not in insts:
                insts[node_port_name] = defaultdict(list)
            insts[node_port_name][node_index].append(neighbor)
            if not get_outgoing and len(insts[node_port_name][node_index]) > 1:
                raise MultipleDriverError(
                    f'Error whilst collecting neighbors: Found multiple drivers for port {node_port_name} (index {node_index}) of instance {n}!'
                )
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

    def split(self, instance: Union[str, Instance]) -> Dict[NonNegativeInt, Instance]:
        """
        Splits the given n-bit large instance into n 1-bit instances.

        Replaces the n-bit large instances by calling their split method.
        The given instance must support splitting. This is the case for all gates, where
        the individual bits are independent of each other (e.g. AND gates, D-FF).
        Instances that do not support splitting are e.g. reduction gates and arithmetic gates.

        Args:
            instance (Union[str, Instance]): The instance or the instance name (must exist in this module).

        Raises:
            ObjectNotFoundError: If no such instance exists in this module.

        Returns:
            Dict[NonNegativeInt, Instance]: A dictionary, where the key is the bit index
                and the value is the corresponding 1-bit "instance slice" for this index.
        """
        if isinstance(instance, Instance):
            instance = instance.name
        if instance not in self.instances:
            raise ObjectNotFoundError(f'No instance {instance} exists in module {self.name}!')
        return self.instances[instance].split()

    def split_all(self, type: str = '', fuzzy: bool = True, recursive: bool = False) -> int:
        """
        Splits all n-bit instances with the given type into n 1-bit instances.

        Each instance that matches the given type (supports fuzzy search, if `fuzzy` is True)
        is split into n slices.
        To split all AND gates, use `Module.split_all("§and")`.
        To split all Flip-Flops, use `Module.split_all("dff", fuzzy=True)`.
        This will split all DFF, ADFF, DFFE, and ADFFE.

        Args:
            type (str, optional): The instance type, where all instances should be split.
                If set to '' and fuzzy is True, all instances inside this module are split. Defaults to ''.
            fuzzy (bool, optional): Whether to perform fuzzy checks.
                If True, the given type string must only be a substring of the instance type. Defaults to True.
            recursive (bool, optional): Whether to perform split operation in submodules as well. Defaults to False.

        Returns:
            int: The number of original instances that were split.
        """
        from netlist_carpentry.utils.gate_lib_base_classes import PrimitiveGate

        splits = 0
        for inst in self.get_instances(type=type, fuzzy=fuzzy):
            if isinstance(inst, PrimitiveGate) and inst.is_primitive and inst.splittable and inst.data_width > 1:
                LOG.debug(
                    f'Splitting {inst.data_width}-bit wide {inst.__class__.__name__} {inst.raw_path} into {inst.data_width} 1-bit wide {inst.__class__.__name__}...'
                )
                self.split(inst)
                splits += 1
        LOG.debug(f'Split {splits} instances in module {self.name}!')
        if recursive:
            for s in self.submodules:
                splits += s.module_definition.split_all(type=type, fuzzy=fuzzy, recursive=True)  # type: ignore
        return splits

    def make_chain(self, instances: List[Instance], input_port: str, output_port: str) -> Tuple[Port[Instance], Port[Instance]]:
        """Forms a chain by chaining the given instances together.

        Each instance in the given list is connected to its successor, where the given
        `output_port` string is the output port of the instance, that is connected
        to the input port `input_port` of the succeeding instance.

        The (unconnected) input port of the first instance and the (unconnected) output port
        of the last instance are returned as a tuple, marking the ends of the chain.

        Each instance must have a port with the given input and output names.

        Args:
            instances (List[Instance]): The instances to chain together.
            input_port (str): The name of the input port that is connected to the predecessor's output port.
            output_port (str): The name of the output port that is connected to the successor's input port.

        Raises:
            ValueError: If the given list is empty.

        Returns:
            Tuple[Port[Instance], Port[Instance]]: The input port of the first instance
                and the output port of the last instance, i.e. the ends of the chain.
        """
        LOG.debug(f'Creating chain of {len(instances)} instances in module {self.name}, connecting port {output_port} to {input_port} each...')
        for i, inst in enumerate(instances):
            if i != 0:
                self.connect(instances[i - 1].ports[output_port], inst.ports[input_port])
        if instances:
            return (instances[0].ports[input_port], instances[-1].ports[output_port])
        else:
            raise ValueError('Cannot make chain: Instance list is empty!')

    def flatten(self, skip_name: Optional[List[str]] = None, skip_type: Optional[List[str]] = None, recursive: bool = False) -> None:
        """
        Flatten this module, by replacing all submodule instances by their module definition.

        Each submodule instance is removed and the content of the module definition is added to this module.
        The previous instance ports are thus connected directly to the instances inside the submodules.

        Args:
            skip_name (Optional[List[str]], optional): Names of submodules, which should not be flattened.
                Defaults to None.
            skip_type (Optional[List[str]], optional): Types of submodules (i.e. module names),
                which should not be flattened. Defaults to None.
            recursive (bool, optional): Whether to also flatten submodules inside the submodules
                (i.e. make this module completely flat). Defaults to False.
        """
        if skip_name is None:
            skip_name = []
        if skip_type is None:
            skip_type = []
        for inst in self.submodules:
            if inst.name not in skip_name and inst.instance_type not in skip_type:
                self._flatten_inst(inst, skip_name, skip_type, recursive)

    def flatten_instance(self, instance: Union[str, Instance]) -> None:
        """Flatten a single instance by replacing the instance with its content.

        This method takes an instance (instance name or object) of this module.
        In this process, the original instance gets replaced with its content.
        This function does not operate recursively, meaning that if the given instance
        has further submodules, they will not be flattened as well.

        Args:
            instance (Union[str, Instance]): The instance (or name of the instance) to flatten.
                Must be part of this module.

        Raises:
            ObjectNotFoundError: If the given instance (or instance name) is not part of this module.
        """
        if isinstance(instance, str):
            if instance not in self.instances:
                raise ObjectNotFoundError(f'No instancce {instance} exists in module {self.name}!')
            instance = self.instances[instance]
        self._flatten_inst(instance, [], [], False)

    def _flatten_inst(self, inst: Instance, skip_name: List[str], skip_type: List[str], recursive: bool) -> None:
        if inst.module_definition is None:
            raise ObjectNotFoundError(f'No module definition found for instance {inst.raw_path}!')
        self._flatten_add_content(inst.name, inst.module_definition)
        self._flatten_connect_interface(inst.name, inst.module_definition, inst.all_connections(include_unconnected=True))
        if recursive:
            for sub_inst in self.submodules:
                sub_inst.module_definition.flatten(skip_name, skip_type, recursive)  # type: ignore[union-attr]
        self.remove_instance(inst)

    def _flatten_add_content(
        self,
        inst_name: str,
        m_inst: Module,
    ) -> None:
        w_paths: Dict[WirePath, WirePath] = {}
        for wire in m_inst.wires.values():
            new_wire = self.create_wire(inst_name + '_' + wire.name, width=wire.width, offset=wire.offset or 0)
            w_paths[wire.path] = new_wire.path
        for mi_inst in list(m_inst.instances.values()):
            new_inst = self.copy_instance(mi_inst, inst_name + '_' + mi_inst.name)
            for pname, conns in mi_inst.connections.items():
                for idx, ws_path in conns.items():
                    if ws_path.raw in CONST_MAP_VAL2OBJ:
                        new_inst.ports[pname][idx].tie_signal(CONST_MAP_VAL2OBJ[ws_path.raw].signal)
                    else:
                        ws_idx = conns[idx].name
                        new_ws_path = WireSegmentPath(raw=w_paths[ws_path.parent].raw + '.' + str(ws_idx))
                        self.connect(new_ws_path, new_inst.ports[pname][idx])

    def _flatten_connect_interface(self, inst_name: str, m_inst: Module, connections: Dict[str, Dict[int, WireSegmentPath]]) -> None:
        for port in m_inst.ports.values():
            for idx, ps in port:
                if port.name in connections:
                    old_port_ws = connections[port.name][idx - (port.offset or 0)]
                    ws_ps = ps.ws.port_segments.copy()
                    ws_ps.remove(ps)
                    for ps in ws_ps:
                        new_inst_name = inst_name + '_' + ps.parent.parent.name
                        new_ps = self.instances[new_inst_name].ports[ps.parent.name][ps.index]
                        new_ps.change_connection()
                        self.connect(old_port_ws, new_ps)
                else:
                    LOG.warn(f'Cannot connect port after flattening: No connection found for port {port.name} of instance {inst_name}!')

    def pre_py2v_hook(self) -> None:
        objs = list(self.ports.values()) + list(self.instances.values()) + list(self.wires.values())
        for obj in objs:
            obj.pre_py2v_hook()

    def post_py2v_hook(self) -> None:
        objs = list(self.ports.values()) + list(self.instances.values()) + list(self.wires.values())
        for obj in objs:
            obj.post_py2v_hook()

    def optimize(self) -> bool:
        """
        Optimizes this module by removing unused wires and instances.

        More optimization algorithms may be implemented in the future.

        Returns:
            bool: True if any changes were made, False otherwise.
        """
        from netlist_carpentry.routines.opt import opt_constant, opt_driverless, opt_loadless

        any_opt = False
        while True:
            any_opt_this_iter = opt_loadless(self)
            any_opt_this_iter |= opt_constant(self)
            any_opt_this_iter |= opt_driverless(self)
            if not any_opt_this_iter:
                break
            any_opt = True
        return any_opt

    def check(self) -> 'CheckReport':
        """Checks this module for issues.

        Returns:
            CheckReport: A report with all found issues.
                bool(CheckReport) returns True if there are issues, and False otherwise.
        """
        from netlist_carpentry.routines.check import CheckReport, fanout, find_comb_loops

        LOG.info(f'Checking module {self.name}...')
        comb_loops = find_comb_loops(self)
        fanout_by_number = fanout(self, sort_by='number')
        return CheckReport(comb_loops={self.name: comb_loops}, fanouts=fanout_by_number)

    @overload
    def show(self) -> None: ...
    @overload
    def show(self, interactive: bool = True) -> Dash: ...
    @overload
    def show(self, interactive: bool = False, figpath: Optional[str] = None, **fwd_params: Optional[object]) -> Optional[Dash]: ...
    def show(self, interactive: bool = False, figpath: Optional[str] = None, **fwd_params: Optional[object]) -> Optional[Dash]:
        from netlist_carpentry.core.graph.visualization import CytoscapeGraph, Plotting

        if fwd_params is None:
            fwd_params = {}

        G = self.graph()
        v = Plotting(G)
        v.set_labels_default()
        if interactive:
            return CytoscapeGraph(G, v.format).get_dash_graph(**fwd_params)
        v.show(figpath=figpath, **fwd_params)
        return None

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
        """Exports this module's metadata in JSON format and writes it to the specified file.

        Args:
            path (Union[str, Path]): The path to a file into which the metadata is written in JSON format.
            include_empty (bool, optional): Whether to include objects without metadata into the normalized dictionary,
                in which case the value is just an empty dictionary. Defaults to False.
            sort_by (Literal[&apos;path&apos;, &apos;category&apos;], optional): Whether the hierarchical path or the
                metadata categories should be the main dictionary keys. Defaults to 'path'.
            filter (Callable[[str, NESTED_DICT], bool], optional): A filter function that takes two parameters, where
                the first represents the metadata category and the second represents the metadata dictionary.
                Defaults to `lambda cat, md: True`, which evaluates to True for all elements and thus does not filter
                anything.
        """
        if isinstance(path, str):
            path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        md_dict = self.normalize_metadata(include_empty=include_empty, sort_by=sort_by, filter=filter)
        with open(path, 'w', encoding='utf-8') as f:
            # ensure_ascii=False: special characters are displayed correctly
            f.write(json.dumps(md_dict, indent=2, ensure_ascii=False))
