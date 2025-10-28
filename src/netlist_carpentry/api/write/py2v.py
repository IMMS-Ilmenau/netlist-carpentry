import datetime
import os
import re
import time
from importlib.metadata import version
from itertools import groupby
from pathlib import Path
from typing import Dict, List

from netlist_carpentry import CFG, CONST_MAP_VAL2OBJ, CONST_MAP_VAL2VERILOG, LOG
from netlist_carpentry.core.circuit import Circuit
from netlist_carpentry.core.exceptions import ObjectNotFoundError
from netlist_carpentry.core.netlist_elements.element_path import WireSegmentPath
from netlist_carpentry.core.netlist_elements.instance import Instance
from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.core.netlist_elements.port import Port
from netlist_carpentry.core.netlist_elements.wire import Wire
from netlist_carpentry.core.netlist_elements.wire_segment import WireSegment
from netlist_carpentry.utils._gate_lib_base import LibUtils


class P2VTransformer:
    def __init__(self) -> None:
        """
        Stores constant wire segments for each module, organized as a nested dictionary.

        Structure:
        {
            "module_name": {
                "module_name.wire_name.index": WireSegment,
                ...
            },
            ...
        }

        Purpose: Tracks wire segments that represent constant values (e.g., 1'b0, 1'b1, 1'bz)
        for Verilog output generation. The nested structure allows efficient lookup
        of constant wires during Verilog code generation, particularly in _constant_wires2v().
        """
        self._constant_wire_segments: Dict[str, Dict[str, WireSegment]] = {}

    def save_circuit2v(self, path: os.PathLike[str], circuit: Circuit, overwrite: bool = False) -> None:
        LOG.info(f'Saving Verilog representation of circuit {circuit.name} to {path}...')
        start = time.time()
        path = Path(path)
        path.parent.mkdir(exist_ok=True)
        mode = 'w' if overwrite else 'x'
        with open(path, mode) as f:
            f.write(
                f'// Generated with NetlistCarpentry {version("netlist-carpentry")}, {datetime.datetime.now().strftime("%d. %B %Y, %H:%M:%S")}\n\n'
            )
            f.write(self.circuit2v(circuit))
        LOG.info(f' Saved Verilog representation of circuit {circuit.name} to {path} in {time.time() - start:.3f} seconds')

    def circuit2v(self, circuit: Circuit) -> str:
        return '\n\n\n'.join(self.module2v(module) for module in circuit)

    def module2v(self, module: Module) -> str:
        params = self._module_params2v(module)
        ports = self._module_ports2v(module)
        wires = self._module_wires2v(module)
        instances = self._module_instances2v(module)
        constant_wires = self._constant_wires2v(module)
        port_wires = self._output_port_wires2v(module)
        module_str = f'module {module.name}{params}{ports};\n{wires}\n{instances}{constant_wires}{port_wires}endmodule'
        return module_str.replace(CFG.id_internal, CFG.id_external)

    def _module_params2v(self, module: Module) -> str:
        param_str = '\n\t#('
        for name in module.parameters:
            param_val = f'"{module.parameters[name]}"' if isinstance(module.parameters[name], str) else str(module.parameters[name])
            param_str += f'\n\t\tparameter {name} = {param_val},'
        return param_str[:-1] + '\n\t)' if module.parameters else ''

    def _module_ports2v(self, module: Module) -> str:
        return '\n\t(' + ','.join(f'\n\t\t{self.port2v(module, p)}' for p in module.ports.values()) + '\n\t)' if module.ports else '()'

    def _module_wires2v(self, module: Module) -> str:
        place_holder = '\t// Wire Definitions'
        return (
            place_holder + ''.join(f'\n\t\t{self.wire2v(module, w)}' for w in module.wires.values() if w.name not in module.ports) + '\n'
            if module.wires
            else ''
        )

    def _module_instances2v(self, module: Module) -> str:
        place_holder = '\t// Primitive Gates and Submodule Instances'
        return place_holder + '\n' + ''.join(self.instance2v(module, i) for i in module.instances.values()) if module.instances else ''

    def instance2v(self, module: Module, instance: Instance) -> str:
        """
        Transform a Python object into a Verilog instance.

        This method takes a Module and an Instance as input, and returns the corresponding Verilog instance.

        Args:
            module (Module): The parent module of the instance.
            instance (Instance): The instance to be transformed into Verilog.

        Returns:
            str: The Verilog representation of the instance.
        """
        LibUtils.change_current_module(module)
        if instance.is_primitive_from_gatelib:
            return self._instance_primitive2v(instance)
        ports_str = self._instance_ports2v(module, instance)
        inst_base = f'{instance.instance_type} {instance.name}({ports_str});'
        return '\n' + ''.join('\t\t' + line + '\n' for line in inst_base.splitlines())

    def _instance_primitive2v(self, instance: Instance) -> str:
        return ''.join('\t\t' + line + '\n' for line in instance.verilog.splitlines())

    def _instance_ports2v(self, module: Module, instance: Instance) -> str:
        ports_strs = []
        for pname in instance.connections:
            verilog_port_str = self._instance_port_connections2v(module, instance.connections[pname])
            ports_strs.append(f'\n\t.{pname}({verilog_port_str})')
        return ','.join(ports_strs) + '\n' if ports_strs else ''

    def _instance_port_connections2v(self, module: Module, port_connections: Dict[int, WireSegmentPath]) -> str:
        wseg_list: List[WireSegment] = []
        for p, k in port_connections.items():
            if k.raw in ['0', '1', 'Z', '']:
                wseg_list.append(CONST_MAP_VAL2OBJ[k.raw])
            else:
                wseg_list.append(module.get_from_path(port_connections[p]))

        return self.simplify_wire_segments(module, list(reversed(wseg_list)))

    @classmethod
    def wire_name_and_index_from_str(cls, module: Module, path: str) -> str:
        """
        Determine the Verilog wire name for a wire in Verilog syntax.

        In Verilog, wire names can be represented in several ways:
            - As a single bit (e.g. `wire w;` and then using it as `w`)
            - As an array of bits (e.g. `wire [7:0] w;` and then using a single segment as `w[3]`, or multiple segments as `{w[3], w[0]}`)

        Args:
            module (Module): The parent module.
            path (str): The hierarchical path to the wire segment (i.e. to which wire it belongs).

        Returns:
            str: The corresponding Verilog wire name for the given constant wire segment.

        """
        wseg_path = WireSegmentPath(raw=path)
        return cls.wire_name_and_index(module, wseg_path)

    @classmethod
    def wire_name_and_index(cls, module: Module, wseg_path: WireSegmentPath) -> str:
        """
        Determine the Verilog wire name for a given wire segment path.

        This method takes a Module and a WireSegmentPath representing a wire segment
        as input, and returns the corresponding Verilog wire name for that wire segment.
        If the wire segment represents a constant value (e.g., 1'b0, 1'b1), it will return
        the corresponding constant Verilog representation.

        Args:
            module (Module): The parent module.
            wseg_path (WireSegmentPath): The WireSegmentPath representing the wire segment path.

        Returns:
            str: The corresponding Verilog wire name for the given wire segment.

        """
        if cls._is_const_wseg_path(wseg_path.raw):
            return cls._get_const_from_wseg_path(wseg_path.raw)
        w = module.get_wire(wseg_path.parent.name)
        return w.name if w.width == 1 else f'{w.name}[{wseg_path.name}]'

    @classmethod
    def _get_const_from_wseg_path(cls, wire_path: str) -> str:
        """
        Determine if a given Verilog wire path corresponds to a constant value.

        Constant wire segments are indicated by their paths, being merely the value of the constant signal.
        In Verilog, constants are represented using the following syntax:
            - defined constants: 1'b0 or 1'b1
            - undefined constant (i. e. unconnected or floating): 1'bx or 1'bz

        Example:
            - `wire_path='1'` returns `1'b1`
            - `wire_path='0'` returns `1'b0`
            - `wire_path='Z'` returns `1'bz`
            - `wire_path='X'` returns `1'bx` (explicitly unconnected)
            - `wire_path=''` returns `1'bx` as well (implicitly unconnected).
            - all other strings will return an empty string.


        Args:
            wire_path (str): The path to check.

        Returns:
            str: The corresponding constant value if the wire path matches a known constant, otherwise an empty string.
        """
        return CONST_MAP_VAL2VERILOG.get(wire_path, '')

    @classmethod
    def _is_const_wseg_path(cls, wire_path: str) -> bool:
        """
        Determine if a given Verilog wire path corresponds to a constant value.

        Args:
            wire_path (str): The path to check.

        Returns:
            bool: True if the wire path matches a constant (e.g. '0', '1', 'Z'), False otherwise.
        """
        return P2VTransformer._get_const_from_wseg_path(wire_path) != ''

    def _constant_wires2v(self, module: Module) -> str:
        if module.name not in self._constant_wire_segments:
            return ''
        LibUtils.change_current_module(module)
        place_holder = '\t// Constant Wires'
        wires = ''
        for wseg_path_raw, wseg in self._constant_wire_segments[module.name].items():
            wseg_path = WireSegmentPath(raw=wseg_path_raw)
            wires += f'\t\tassign {self.wire_name_and_index(module, wseg_path)}\t= {self._get_const_from_wseg_path(wseg.raw_path)};\n'
        return place_holder + '\n' + wires

    def _output_port_wires2v(self, module: Module) -> str:
        """
        Returns a string of Verilog assignments for output ports.

        This method generates Verilog code that assigns internal wires to the corresponding output ports.
        It **only** includes output ports that are connected to specific internal wires and **not assigned directly**
        to an instance or a primitive operator, e. g. via `assign OutputPort = wire1 & wire2;`
        or `Instance(.somePort(OutputPort), ... );`.
        This method produces a string following the scheme `assign OutputPort = internal_wire;`.

        Args:
            module (Module): The parent module.

        Returns:
            str: A string of assignment statements for the output ports, or an empty string if no assignments are needed.
        """
        port_wire_strs = []
        for p in module.output_ports:
            for s in p.segments.values():
                pname = p.name if p.width == 1 else f'{p.name}[{s.index}]'
                wname = self.wire_name_and_index(module, s.ws_path)
                if pname != wname:
                    # Port is connected to internal wire and not explicitely connected beforehand
                    # Otherwise this would lead to 'assign PortName = PortName;'
                    port_wire_strs.append(f'\t\tassign {pname}\t= {wname};')
        port_wire_strs.sort()
        if port_wire_strs:
            place_holder = '\t// Output Wires'
            return place_holder + '\n' + '\n'.join(port_wire_strs) + '\n\n'
        return ''

    def wire2v(self, module: Module, wire: Wire) -> str:
        """
        Converts a netlist wire to a wire or reg in Verilog syntax, depending on its driving instance.

        Args:
            module (Module): The module to which this wire belongs to.
            wire (Wire): The netlist wire to convert.

        Returns:
            str: The Verilog instantiation of the wire, either as `reg` or `wire`.

        Example 1:
            ```python
            >>> from netlist_carpentry.core.netlist_elements.module import Module
            >>> from netlist_carpentry.core.netlist_elements.wire import Wire
            >>> module = Module(raw_path='module1')
            >>> wire = Wire(raw_path='module1.wire1', width=8)
            >>> module.add_wire(wire)
            >>> transformer = P2VTransformer()
            >>> print(transformer.wire2v(module, wire))
            'wire [7:0] wire1;'
            ```

        Example 2:
            ```python
            >>> from netlist_carpentry.core.netlist_elements.module import Module
            >>> from netlist_carpentry.core.netlist_elements.wire import Wire
            >>> from netlist_carpentry.utils.gate_lib import DFF
            >>> module = Module(raw_path='module1')
            >>> dff = DFF(raw_path='module1.dff1')
            >>> wire = Wire(raw_path='module1.wire1', width=8)
            >>> module.add_wire(wire)
            >>> module.add_instance(dff1)
            >>> module.connect(dff.ports['Q'].path, wire[0].path)  # Connect wire to a Flip-Flop -> wire becomes a reg
            >>> transformer = P2VTransformer()
            >>> print(transformer.wire2v(module, wire))
            'reg [7:0] wire1;'
            ```
        """
        wire_prefix = self._net_type(module, wire)
        offset = min(wire.segments.keys())
        correct_indexing = f' [{wire.width + offset - 1}:{offset}]' if wire.msb_first else f' [{offset}:{wire.width + offset - 1}]'
        width_str = correct_indexing if wire.width > 1 else '\t'
        for index, segment in wire:
            if self._get_const_from_wseg_path(segment.raw_path):
                if module.name not in self._constant_wire_segments:
                    self._constant_wire_segments[module.name] = {}
                seg_path = f'{module.name}.{wire.name}.{index}'
                self._constant_wire_segments[module.name][seg_path] = CONST_MAP_VAL2OBJ[segment.raw_path]
        return f'{wire_prefix}{width_str}\t{wire.name};'

    def _net_type(self, module: Module, wire: Wire) -> str:
        """
        Determine whether a netlist wire should be instantiated as 'reg' or 'wire' in Verilog syntax.

        This method checks the driving instances of the given wire (which ideally should only be one!).
        If the wire is driven by e.g. a flip-flop or latch, it returns 'reg ' (with trailing whitespace
        for formatting reasons), indicating that the wire should be declared as a register.
        Otherwise, it returns 'wire'.

        Args:
            module (Module): The parent module of the wire.
            wire (Wire): The netlist wire to check.

        Returns:
            str: Either 'reg ' or 'wire', depending on the driving instances of the wire.
        """
        for s in wire.segments.values():
            if not s.is_constant:
                for dr in module.get_driving_ports(s.path):
                    inst_name = dr.path.nth_parent(2).name
                    if inst_name in module.instances:  # Otherwise, driving node is a module port
                        inst = module.instances[inst_name]
                        if 'dff' in inst.instance_type or 'dlatch' in inst.instance_type:
                            return 'reg '
        return 'wire'

    def port2v(self, module: Module, port: Port[Module]) -> str:
        """
        Converts a Python Port object into its corresponding Verilog string, representing a module port.

        This method takes into account the direction and width of the port to generate the correct Verilog syntax.

        Args:
            module (Module): The module to which this port belongs to.
            port (Port): The Port object to be converted.

        Returns:
            str: The Verilog string representation of the port.

        Example:
            >>> from netlist_carpentry.core.netlist_elements.port import Port
            >>> port = Port(name='port1', direction='input', width=8)
            >>> transformer = P2VTransformer()
            >>> print(transformer.port2v(port))
            'input [7:0] port1'
        """
        if port.name not in module.wires:
            raise ObjectNotFoundError(f'No corresponding wire found for port {port.raw_path}!')
        net_type = self._net_type(module, module.wires[port.name])
        offset = min(port.segments.keys())
        correct_indexing = f'[{port.width + offset - 1}:{offset}]' if port.msb_first else f'[{offset}:{port.width + offset - 1}]'
        width_str = correct_indexing if port.width > 1 else '\t'
        return f'{port.direction.value}\t{net_type}\t{width_str}\t{port.name}'

    @classmethod
    def simplify_wire_segments(cls, module: Module, wire_segments: List[WireSegment]) -> str:
        """
        Simplify a list of WireSegments into a Verilog-compatible concatenation.

        This function takes a list of WireSegments and groups them by their wire name.
        Then, it sorts the segments within each group in descending order and formats them
        according to the Verilog syntax for concatenating bits. The resulting string is either
        a single bit assignment or a concatenated bit assignment.

        For example, given a list of WireSegments with indices [3, 1, 0], the function would return '{wire[3], wire[1:0]}'.
        If there are multiple groups, they will be comma-separated within the concatenation brackets.
        If the index list matches the full wire in correct order, the indexing is dropped completely, since it is not required.

        Args:
            module (Module): The parent module.
            wire_segments (List[WireSegment]): A list of WireSegments to simplify.

        Returns:
            str: A Verilog-compatible string representing the concatenated wire segments.
        """
        grouped_list = [list(group) for _, group in groupby(wire_segments, key=lambda x: cls._is_const_wseg_path(x.raw_path) or x.super_wire_name)]
        formatted_wires: List[str] = []
        for wlist in grouped_list:
            if all(cls._is_const_wseg_path(w.raw_path) for w in wlist):
                formatted_wires.append(cls._simplify_constant_wire_segments(wlist))
            else:
                # Parse names and indices
                parsed: List[re.Match] = [re.match(r'([\S ]+?|\w+)(?:\s*)\[(\d+)(?::(\d+))?\]', f'{w.super_wire_name}[{w.index}]') for w in wlist]

                base_wire_name = parsed[0].group(1)
                wire = module.get_wire(base_wire_name)
                indices = [int(m.group(2)) for m in parsed]

                # Group consecutive indices
                index_groups = cls._group_indices(indices)

                # Format groups into Verilog slice or single
                formatted_wires.extend(cls._format_single_wire(index_groups, wire))
        if len(formatted_wires) == 1:
            return formatted_wires[0]
        return '{' + ', '.join(formatted_wires) + '}'

    @classmethod
    def _simplify_constant_wire_segments(cls, wire_segments: List[WireSegment]) -> str:
        """
        Converts the signals of a given list of wire segments to an expression in Verilog syntax.

        For each wire segment of the given list, the signal is retrieved.
        For constant wire segments, this value corresponds to '0', '1', or 'Z'.
        All provided wire segments are concatenated to form the final expression.
        It is therefore necessary that all wire segments are constant.
        Non-constant wire segments will result in 'x' in the Verilog representation.

        Args:
            wire_segments (List[WireSegment]): A list of WireSegments with constant signal values.

        Returns:
            str: The Verilog representation of the concatenated bits.
        """
        sig_str = ''.join(str(w.signal.value) for w in wire_segments)
        pad_sig_str = sig_str.zfill(len(wire_segments))
        return f"{len(wire_segments)}'b{pad_sig_str}"

    @classmethod
    def _group_indices(cls, indices: List[int]) -> List[List[int]]:
        """
        Group a list of integers into sublists where each sublist contains (descending) consecutive integers.

        This method is required for grouping wire indices into consecutive sublists.
        If the original wire list is e. g. `[wire[3], wire[2], wire[1], wire[0]]`, the given index list is `[3, 2, 1, 0]`.
        In this list, all integeres are consecutive (descending).
        Thus, no further grouping is required, and the result is `[ [3, 2, 1, 0] ]`.
        However, for a wire list `[wire[3], wire[0]]`, the given index list is `[3, 0]`.
        Here, grouping is required (since 3 does not directly follow to 0), and the result is `[ [3], [0] ]`.

        This does not work vice versa, e. g. for a wire list `[wire[0], wire[1], wire[2], wire[3]]`,
        the given index list is  `[ [0], [1], [2], [3]]` and **not** `[ [0, 1, 2, 3] ]`.
        Verilog does not allow vector slicing with LSB-first, only MSB-first.
        So, `wire[3:0]` is allowed, but not `wire[0:3]`!

        Args:
            indices (List[int]): The list of integers to group.

        Returns:
            List[List[int]]: A list of lists containing the grouped (descending) consecutive integers.
        """
        groups = []
        group = [indices[0]]
        for current, next_ in zip(indices, [*indices[1:], None]):
            if next_ is not None and next_ == current - 1:
                group.append(next_)
            else:
                groups.append(group)
                if next_ is not None:
                    group = [next_]
        return groups

    @classmethod
    def _format_single_wire(cls, index_groups: List[List[int]], wire: Wire) -> List[str]:
        """
        Format a list of consecutive integer indices of a given wire into Verilog-compatible syntax for concatenating bits.

        This method takes a list of consecutive integer indices and formats them according to the Verilog syntax
        for concatenating bits. The resulting string can be either a single bit assignment (e.g., 'wire[3]') or a
        concatenated bit assignment (e.g., '{wire[3], wire[1:0]}'). If there are multiple groups of consecutive
        indices, they will be comma-separated within the concatenation brackets. If the index list matches the full
        wire in correct order, the indexing is dropped completely, since it is not required.

        Args:
            index_groups (List[List[int]]): A list of lists containing the grouped (descending) consecutive integers.
            wire (Wire): The Wire object associated with the indices.

        Returns:
            List[str]: A list of strings representing the formatted wire segments in Verilog syntax.
        """
        formatted_wire = []
        for g in index_groups:
            no_idx = all(index in wire.segments for index in g) and all(index in g for index in wire.segments)
            indexing = f'[{g[0]}:{g[-1]}]' if len(g) > 1 else f'[{g[0]}]'
            formatted_wire_part = f'{wire.name}{"" if no_idx else indexing}'
            formatted_wire.append(formatted_wire_part)
        return formatted_wire
