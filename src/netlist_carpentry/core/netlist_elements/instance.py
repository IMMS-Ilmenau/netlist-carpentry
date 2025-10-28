from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Dict, Iterable, Literal, Optional, Tuple, Union

from pydantic import BaseModel
from typing_extensions import Self

from netlist_carpentry import CFG, LOG, WIRE_SEGMENT_X
from netlist_carpentry.core.exceptions import (
    IdentifierConflictError,
    ObjectLockedError,
    ObjectNotFoundError,
    ParentNotFoundError,
)
from netlist_carpentry.core.netlist_elements.element_path import InstancePath, WireSegmentPath
from netlist_carpentry.core.netlist_elements.element_type import EType
from netlist_carpentry.core.netlist_elements.mixins.metadata import METADATA_DICT, NESTED_DICT
from netlist_carpentry.core.netlist_elements.netlist_element import NetlistElement
from netlist_carpentry.core.netlist_elements.port import Port
from netlist_carpentry.core.netlist_elements.port_segment import PortSegment
from netlist_carpentry.core.netlist_elements.wire_segment import CONST_MAP_VAL2OBJ
from netlist_carpentry.core.port_direction import PortDirection
from netlist_carpentry.core.protocols.signals import LogicLevel
from netlist_carpentry.utils.custom_dict import CustomDict

if TYPE_CHECKING:
    from netlist_carpentry.core.netlist_elements.module import Module


class Instance(NetlistElement, BaseModel):
    instance_type: str
    """
    Name of the module this instance represents.

    For primitives (such as gates or flip-flops), the name references a cell from the built-in library.
    """

    _ports = CustomDict[str, Port['Instance']]()
    is_primitive: bool = False
    """
    Flag indicating whether the instance represents a primitive element.

    If True, this instance corresponds to a basic component such as a gate or flip-flop,
    rather than a module instance composed of other instances.
    """
    module: Optional[NetlistElement] = None

    def model_post_init(self, __context: Optional[Dict[str, object]]) -> None:
        from netlist_carpentry.core.netlist_elements.module import Module

        if self.module is None or isinstance(self.module, Module):
            return super().model_post_init(__context)
        raise TypeError(f'Instance.module {self.raw_path} should be a module, but is a {type(self.module).__name__}!')

    @property
    def path(self) -> InstancePath:
        """
        Returns the InstancePath of the netlist element.

        The InstancePath object is constructed using the element's type and its raw hierarchical path.

        Returns:
            InstancePath: The hierarchical path of the netlist element.
        """
        return InstancePath(raw=self.raw_path)

    @property
    def type(self) -> EType:
        """The type of the element, which is an instance."""
        return EType.INSTANCE

    @property
    def parent(self) -> Module:
        from netlist_carpentry.core.netlist_elements.module import Module

        if isinstance(self.module, Module):
            return self.module
        elif self.module is None:
            raise ParentNotFoundError(
                f'No parent module specified for instance {self.raw_path}. '
                + 'This is probably due to a bad instantiation (missing or bad "module" parameter), or a subsequent modification of the module, which corrupted the instance.'
            )
        raise TypeError(f'Bad type: Parent object of instance {self.raw_path} is {type(self.module).__name__}, but should be {Module.__name__}')

    @property
    def connections(self) -> Dict[str, Dict[int, WireSegmentPath]]:
        """
        A dictionary mapping port names to their corresponding connection paths.

        The keys of the outer dictionary are the names of the ports.
        The values are dictionaries where the keys are the port bit numbers and the values are WireSegmentPath objects.
        The element paths are the paths of the wires connected to the corresponding bits of the port.
        Elements with no connection (i.e. the path is `None`) are excluded.
        In case these are needed, use Instance.get_connections() instead.

        Example:
            {
                'port1': {1: WireSegmentPath('path/to/element1'), 2: WireSegmentPath('path/to/element2')},
                'port2': {1: WireSegmentPath('path/to/element3')}
            }
        """
        return self.all_connections(include_unconnected=True)

    def all_connections(self, include_unconnected: bool) -> Dict[str, Dict[int, WireSegmentPath]]:
        """
        Returns a dictionary mapping port names to their corresponding connection paths.

        The keys of the outer dictionary are the names of the ports.
        The values are dictionaries where the keys are the port bit numbers and the values are WireSegmentPath objects.
        The element paths are the paths of the wires connected to the corresponding bits of the port.

        Args:
            include_unconnected (bool): Whether to include unconnected ports in the result.

        Returns:
            A dictionary mapping port names to their corresponding connection paths.
        """
        conn = CustomDict[str, Dict[int, WireSegmentPath]]()
        for pname in self.ports:
            p = self.ports[pname]
            for s in p.segments:
                if p[s].is_connected or include_unconnected:
                    conn_dict = {s: p[s].ws_path}
                    conn.update_or_create(pname, conn_dict)
        return conn

    @property
    def connection_str_paths(self) -> Dict[str, Dict[int, str]]:
        """
        Returns a dictionary mapping port names to their corresponding connection paths as strings.

        The keys are the names of the ports.
        The values are dictionaries where the keys are the port bit numbers and the values are the raw string paths.

        Example:
            {
                'port1': {0: 'path.to.element1', 1: 'path.to.element2'},
                'port2': {0: 'path.to.element3'}
            }
        """
        return {p: {idx: path.raw for idx, path in conn_dict.items()} for p, conn_dict in self.connections.items()}

    @property
    def ports(self) -> CustomDict[str, Port[Instance]]:
        """
        A dictionary mapping port names to their corresponding Port objects.

        The keys of the dictionary are the names of the ports.
        The values are Port objects representing the ports.

        Returns:
            A dictionary mapping port names to their corresponding Port objects.
        """
        return self._ports

    @property
    def input_ports(self) -> Tuple[Port[Instance], ...]:
        """
        Returns a tuple of input ports associated with this instance.

        This property filters the ports based on their direction, returning only those that are marked as inputs.

        Returns:
            A tuple of Port objects representing the input ports.
        """
        return tuple(p for p in self.ports.values() if p.is_input)

    @property
    def output_ports(self) -> Tuple[Port[Instance], ...]:
        """
        Returns a tuple of output ports associated with this instance.

        This property filters the ports based on their direction, returning only those that are marked as outputs.

        Returns:
            A tuple of Port objects representing the output ports.
        """
        return tuple(p for p in self.ports.values() if p.is_output)

    @property
    def is_module_instance(self) -> bool:
        """
        Checks whether this instance represents a module instance rather than a primitive element.

        This property returns True if the instance is not marked as primitive, indicating that it corresponds to a higher-level module composed of other instances.

        Returns:
            A boolean flag indicating whether this instance represents a module instance.
        """
        return not self.is_primitive

    @property
    def is_primitive_from_gatelib(self) -> bool:
        """
        Check if the instance type is a primitive from the gate library.

        This property checks if the instance type starts with the internal identifier used for
        primitive gates and if it exists in the gate library.

        Returns:
            bool: True if the instance type is a primitive from the gate library, False otherwise.
        """
        from netlist_carpentry.utils.gate_lib import get

        return self.instance_type[0] == CFG.id_internal and get(self.instance_type) is not None

    @property
    def verilog_template(self) -> str:
        """
        Verilog template string for instantiating this instance.

        This property returns a template string in the format of a Verilog module instantiation.
        The string contains placeholders for the instance type, name, and ports.
        The syntax is as follows: `<instance_type> <instance_name> (<port_connections>);`
        where:
            - `<instance_type>` is the type of the instance (e.g., a module or primitive),
            - `<instance_name>` is the unique identifier for this instance,
            - `<port_connections>` is a list of port connections in the format `.port_name(wire_name)`.

        For example, if we have an instance of type `my_module` with ports `input_port` and `output_port`,
        connected to wires `input_wire` and `output_wire`, respectively, the resulting Verilog code would be:
            `my_module my_instance (.input_port(input_wire), .output_port(output_wire));`

        Returns:
            str: The Verilog template string.
        """
        return '{inst_type} {inst_name} ({ports});'

    @property
    def verilog(self) -> str:
        """
        Generates the Verilog code for this instance.

        This property uses the `verilog_template` to generate the actual Verilog code by replacing the placeholders with
        the instance type, name, and port connections. It returns a string that can be used directly in a Verilog file.

        Returns:
            str: The generated Verilog code.
        """
        return self.verilog_template.format(inst_type=self.instance_type, inst_name=self.name, ports=self._verilog_ports())

    def _verilog_ports(self) -> str:
        """
        Generate the port assignments for a Verilog instance instantiation.

        This method iterates over each port of the instance and generates a string that represents the port connections.
        The format of the string is `.port_name(wire_name)`, where `wire_name` is the name of the wire connected to the port.
        If a port has multiple bits, the wire names are enclosed in curly brackets and separated by commas.

        Returns:
            str: A string representing the port assignments for the Verilog instance instantiation.

        Example:
            For an instance with two ports, `input_port` and `output_port`, connected to wires `input_wire` and `output_wire`,
            respectively, the resulting string would be:
                `.input_port(input_wire), .output_port(output_wire)`
        """
        port_str = ''
        for p in self.ports.values():
            if len(p) == 1:
                # If the port has only one bit, directly use the wire name
                sigs = self._verilog_wire_name(next(iter(p.segments.values())))
            else:
                # If the port has multiple bits, enclose the wire names in curly brackets and separate them with commas
                sigs = '{' + ', '.join(self._verilog_wire_name(s) for s in p.segments.values()) + '}'
            # Append the port assignment to the result string
            port_str += f'\n\t.{p.name}({sigs}),'
        # Remove the trailing comma and return the result string
        return port_str[:-1] + '\n' if port_str else port_str

    def _verilog_wire_name(self, seg: PortSegment) -> str:
        """
        Generate the Verilog wire name for a given port segment.

        This method takes a `PortSegment` object as input and returns the corresponding Verilog wire name.
        If the segment has no connection (i.e., its raw wire segment path is empty), it returns "1'bz".
        Otherwise, it constructs the wire name by concatenating the module and bit indices from the segment's wire path.

        Args:
            seg: The port segment for which to generate the Verilog wire name.

        Returns:
            str: The generated Verilog wire name.
        """
        return "1'bz" if seg.is_unconnected else f'{seg.ws_path.parent.name}[{seg.ws_path.name}]'

    def port_is_known(self, port_name: str) -> bool:
        """
        Check whether a given port name is known to this instance.

        This method checks if the provided `port_name` exists as a key in the instance's ports dictionary.

        Args:
            port_name (str): The name of the port to check for existence.

        Returns:
            bool: True if the port is known, False otherwise.
        """
        return port_name in self.ports

    def _connect_single(
        self, port_name: str, ws_path: Optional[WireSegmentPath], direction: PortDirection = PortDirection.UNKNOWN, index: int = 0
    ) -> PortSegment:
        """
        Establish a single connection between this instance's port and a given wire segment.

        This method either adds the connection to an existing port or creates a new port if it doesn't exist yet.

        Args:
            port_name (str): The name of the port where the connection should be established.
            ws_path (WireSegmentPath): The path of the wire segment that will be connected to this port.
            direction (PortDirection, optional): The direction of the port. Defaults to PortDirection.UNKNOWN.
            index (int, optional): The bit index within the port for this connection. Defaults to 0.

        Returns:
            PortSegment: The port segment with the new connection that was added.
        """
        if self.port_is_known(port_name):
            port = self.ports[port_name]
        else:
            port = Port(raw_path=f'{self.path.raw}.{port_name}', direction=direction, module_or_instance=self)
            self.ports.add(port_name, port, locked=self.locked)
        ws_path = ws_path.raw if ws_path is not None else ''
        try:
            return port.create_port_segment(index).set_ws_path(ws_path)
        except IdentifierConflictError as e:
            raise IdentifierConflictError(
                f'Unable to add port {port_name} (index {index}) to instance {self.name}!'
                + 'This is probably because either a port with this name already exists, or because the index is already occupied.'
            ) from e

    def connect(
        self,
        port_name: str,
        ws_path: Optional[WireSegmentPath],
        direction: PortDirection = PortDirection.UNKNOWN,
        index: int = 0,
        width: int = 1,
    ) -> None:
        """
        Add connections to the specified port of this instance.

        This method can establish multiple connections if a range of indices is provided.

        Args:
            port_name (str): The name of the port where the connection(s) should be established.
            ws_path (Optional[WireSegmentPath]): The path of the wire segment that will be connected to this port.
                If None, the associated port (segment) remains unconnected.
            direction (PortDirection, optional): The direction of the port. Defaults to PortDirection.UNKNOWN.
            index (int, optional): The starting bit index within the port for these connections. Defaults to 0.
            width (int, optional): The number of consecutive bits in the port that should be connected. Defaults to 1.

        Raises:
            ObjectLockedError: If this instance is currently locked, and no connection can be made.
        """
        if self.locked:
            raise ObjectLockedError(f'Cannot add connection: Instance {self.path} is currently locked!')
        for i in range(index, index + width):
            self._connect_single(port_name, ws_path, direction, i)

    def disconnect(self, port_name: str, index: int) -> None:
        """
        Remove an existing connection from a specified port of this instance.

        This method disconnects the wire segment at the given `index` within the specified `port_name`.

        Args:
            port_name (str): The name of the port where the connection should be removed.
            index (int): The bit index within the port for this disconnection.

        Raises:
            ObjectLockedError: If this instance is locked.
            ObjectNotFoundError: If no port exists with the given name.
        """
        if self.locked:
            raise ObjectLockedError(f'Cannot remove connections from instance {self.raw_path}: Instance locked!')
        if port_name not in self.ports:
            raise ObjectNotFoundError(f'Instance {self.path} has no port {port_name}!')
        return self.ports[port_name].change_connection(WIRE_SEGMENT_X.path, index)

    def get_connection(self, port_name: str, index: int = -1) -> Union[WireSegmentPath, Dict[int, WireSegmentPath], None]:
        """
        Retrieve the connection path associated with a specified port and bit index.

        If `index` is provided, this method returns the wire segment path connected to that specific bit within the port.
        Otherwise, it returns all connections for the given port as a dictionary mapping indices to WireSegmentPaths.

        Args:
            port_name (str): The name of the port for which to retrieve the connection(s).
            index (int, optional): The bit index within the port. Defaults to -1.

        Returns:
            Union[WireSegmentPath, Dict[int, WireSegmentPath]]: Either a single WireSegmentPath or a dictionary mapping indices to WireSegmentPaths.
        """
        if index == -1:
            return self.connections.get(port_name, {})
        return self.connections[port_name].get(index, None)

    def modify_connection(self, port_name: str, ws_path: WireSegmentPath, index: int = 0) -> None:
        """
        Modify an existing connection within a specified port of this instance.

        This method updates the wire segment path at the given `index` within the specified `port_name`.
        If the index does not exist yet, it is newly added, changing the width of the port.

        Args:
            port_name (str): The name of the port where the connection should be modified.
            ws_path (WireSegmentPath): The new wire segment path for this connection.
            index (int, optional): The bit index within the port. Defaults to 0.
        """
        is_locked = self.locked or self.ports[port_name].locked if port_name in self.ports else self.locked
        if is_locked:
            raise ObjectLockedError(f'Cannot modify connection: Instance {self.path} is currently locked!')
        port = self.ports.get(port_name, None)
        if port is not None:
            # The index is not initialized yet, i.e. no wire segment for this index is present
            if index not in port.segments:
                port.create_port_segment(index).set_ws_path(ws_path.raw)
            # The wire segment at the given index is connected to a different wire
            elif port[index].raw_ws_path != ws_path.raw:
                port[index].set_ws_path(ws_path.raw)
                self.ports.remove(port_name, locked=self.locked)
                self.ports.add(port_name, port, locked=self.locked)
            else:
                LOG.info(
                    f'Connection of port {self.raw_path}{self.path.sep}{port_name}{self.path.sep}{index}->{ws_path.raw} exists already, nothing is changed...'
                )
        else:
            raise ObjectNotFoundError(f'Cannot modify connection: No port {port_name} exists for instance {self.raw_path}')

    def connect_modify(
        self, port_name: str, ws_path: WireSegmentPath, direction: PortDirection = PortDirection.UNKNOWN, index: int = 0, width: int = 1
    ) -> None:
        """
        Add a new connection or modify an existing one within the specified port of this instance.

        If the connection already exists at the given `index` and `port_name`, it will be modified.
        Otherwise, a new connection is added.

        Args:
            port_name (str): The name of the port where the connection should be established or updated.
            ws_path (WireSegmentPath): The path of the wire segment that will be connected to this port.
            direction (PortDirection, optional): The direction of the port. Defaults to PortDirection.UNKNOWN.
            index (int, optional): The starting bit index within the port for these connections. Defaults to 0.
            width (int, optional): The number of consecutive bits in the port that should be connected. Defaults to 1.
        """
        if port_name not in self.ports or index not in self.ports[port_name].segments:
            return self.connect(port_name, ws_path, direction, index, width)
        self.modify_connection(port_name, ws_path, index)

    def tie_port(self, name: str, index: int, sig_value: LogicLevel) -> None:
        """
        Set a constant signal value for the specified port and bit index.

        If the specified port does not exist, an error message is logged and the function returns False.
        Otherwise, the method tries to set the constant signal value for that port and returns True if successful.

        **Does not work for instance output ports, as they are always driven by their parent instances.**

        Args:
            name (str): The name of the port.
            index (int): The bit index within the port.
            sig_value (LogicLevel): The constant signal value to be set ('0', '1', or 'Z').

        Raises:
            ObjectNotFoundError: If no such port or port segment exists.
            AlreadyConnectedError: (raised by: PortSegment.tie_signal) If this segment is belongs to a load port and is already connected to a wire,
                from which it receives its value.
            InvalidPortDirectionError: (raised by: PortSegment.tie_signal) If this port segment belongs to an instance output port,
                which is driven by the instance inputs and the instance's internal logic.
            InvalidSignalError: (raised by: PortSegment.tie_signal) If an invalid value is provided.
        """
        if name not in self.ports:
            raise ObjectNotFoundError(f'No such port {name} exists in instance {self.raw_path}!')
        self.ports[name].tie_signal(sig_value, index)

    def has_tied_ports(self) -> bool:
        """
        Checks the ports of this instance whether any are tied to constant values.

        Instance ports can be tied to a constant value for several reasons, but if all input
        or all output ports are tied, the instance is rendered useless.

        Returns:
            bool: True if any ports of this instance are tied to constant values.
                False otherwise, i.e. all ports are connected to wires.
        """
        return self.has_tied_inputs() or self.has_tied_outputs()

    def has_tied_inputs(self) -> bool:
        """
        Checks the input ports of this instance whether any are tied to constant values.

        Instance ports can be tied to a constant value for several reasons, but if all input
        or all output ports are tied, the instance is rendered useless.

        Returns:
            bool: True if any input ports of this instance are tied to constant values.
                False otherwise, i.e. all input ports are connected to wires.
        """
        return self._any_tied(self.input_ports)

    def has_tied_outputs(self) -> bool:
        """
        Checks the output ports of this instance whether any are tied to constant values.

        Instance ports can be tied to a constant value for several reasons, but if all input
        or all output ports are tied, the instance is rendered useless.

        Returns:
            bool: True if any output ports of this instance are tied to constant values.
                False otherwise, i.e. all output ports are connected to wires.
        """
        return self._any_tied(self.output_ports)

    def _any_tied(self, ports: Iterable[Port[Instance]]) -> bool:
        """Checks the given port tuple for constant ports, i.e. ports tied to a constant value.

        Args:
            ports (Iterable[Port]): An iterable containing the ports to check.

        Returns:
            bool: True if at least one port is tied to a constant value.
                False otherwise, i.e. all ports are connected to wires.
        """
        return any(s.raw_ws_path in CONST_MAP_VAL2OBJ for p in ports for s in p.segments.values())

    def _set_name_recursively(self, old_name: str, new_name: str) -> None:
        for p in self.ports.values():
            p.raw_path = p.path.replace(old_name, new_name).raw
            for _, ps in p:
                ps.raw_path = ps.path.replace(old_name, new_name).raw

    def change_mutability(self, is_now_locked: bool, recursive: bool = False) -> Self:
        """
        Change the mutability status of this instance and optionally its ports.

        This method allows setting whether this instance can be modified or not.
        If `recursive` is set to True, it also applies the same mutability status to all ports of this instance.

        Args:
            is_now_locked (bool): The new mutability status for this instance.
            recursive (bool, optional): Whether to apply the change recursively to its ports. Defaults to False.
        """
        if recursive:
            for p in self.ports.values():
                p.change_mutability(is_now_locked=is_now_locked)
        return super().change_mutability(is_now_locked)

    def normalize_metadata(
        self,
        include_empty: bool = False,
        sort_by: Literal['path', 'category'] = 'path',
        filter: Callable[[str, NESTED_DICT], bool] = lambda cat, md: True,
    ) -> METADATA_DICT:
        md = super().normalize_metadata(include_empty=include_empty, sort_by=sort_by, filter=filter)
        for p in self.ports.values():
            s_md = p.normalize_metadata(include_empty=include_empty, sort_by=sort_by, filter=filter)
            for cat, val in s_md.items():
                if cat in md:
                    md[cat].update(val)
                else:
                    md[cat] = val
        return md

    def __hash__(self) -> int:
        return hash((self.raw_path, self.instance_type, self.is_primitive, tuple(hash(p) for p in self.ports.values())))

    def __str__(self) -> str:
        return f'{self.__class__.__name__} "{self.name}" with path {self.path.raw} (type {self.instance_type})'

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.instance_type}: {self.path.raw})'
