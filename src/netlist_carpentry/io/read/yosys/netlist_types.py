"""Collection of TypedDicts to simplify handling of Yosys-generated JSON netlists."""

import os
import re
import warnings
from typing import Callable, Dict, List, Literal, Optional, Set, Tuple, Union

from pydantic import BaseModel, PositiveInt

from netlist_carpentry import CFG, CONST_MAP_YOSYS2OBJ, LOG, Direction, Instance, Module, NetlistElement, Port, Signal, Wire
from netlist_carpentry.core.enums.signal import T_SIGNAL_STATES
from netlist_carpentry.core.netlist_elements.element_path import WireSegmentPath
from netlist_carpentry.utils.gate_lib import get
from netlist_carpentry.utils.gate_lib_dataclasses import PortParams, WireParams

BitAlias = Union[int, T_SIGNAL_STATES]
PortDirections = Dict[str, Literal['input', 'output', 'inout']]


class NetlistContent(BaseModel):
    model_config = {'extra': 'allow'}

    attributes: Optional[Dict[str, str]] = None

    def __contains__(self, item: str) -> bool:
        return item in self.model_fields_set

    def __len__(self) -> int:
        return len(self.model_fields_set)

    def clean(self) -> None:
        """Cleans the input data by replacing all special characters in identifiers with `CFG.id_internal`."""
        pass

    def _clean_str(self, dict_entry: str) -> str:
        return re.sub(r'[^A-Za-z0-9_]', CFG.id_internal, dict_entry)

    def replace(self, old: str, new: str) -> None:
        """Replaces all occurences of `old` in strings in the input data with `new`.

        This affects all forms of names (attribute names and values, port names, instance names and types, wire names).
        This does not affect module and instance parameters, as well as values that are not strings.

        As an example, `NetlistContent.replace("moduleName", "moduleName2")` will replace every "moduleName" found in
        the netlist data with "moduleName2".

        Args:
            old (str): The old/current substring to replace everywhere.
            new (str): The new substring to insert everywhere, where `old` was previously.
        """
        pass

    @staticmethod
    def _try_get_int(val: Union[str, int]) -> Union[int, str]:
        if isinstance(val, int):
            return val
        if all(c == '0' or c == '1' for c in val) and val:
            return int(val, 2)
        return val

    def build_metadata(self, obj: NetlistElement) -> None:
        """Builds the metadata from the attributes dictionary and applies it to the given object.

        `obj.metadata.yosys[attribute_name]` can be used to refer to any attribute from the JSON netlist
        that was introduced by Yosys.

        Args:
            obj (NetlistElement): The object onto which the metadata from the attributes dictionary is applied.
        """
        if self.attributes:
            obj.metadata.add_category('yosys')
            for attr_name, attr_val in self.attributes.items():
                obj.metadata.yosys[attr_name] = self._try_get_int(attr_val)


class PortData(NetlistContent):
    direction: Optional[str] = None
    bits: Optional[List[BitAlias]] = None
    upto: Optional[int] = None
    offset: Optional[int] = None
    signed: Optional[int] = None

    def build_port(self, net_number_map: Dict[PositiveInt, WireSegmentPath], module: Module, port_name: str) -> Port[Module]:
        """Builds a port object from the data of this object and the given name and adds it to the given module.

        The `net_number_map` is required to map connection numbers to actual wires from the given module.

        Args:
            net_number_map (Dict[PositiveInt, WireSegmentPath]): A dictionary mapping connection numbers
                to wire segments from the given module.
            module (Module): The module for which a port is created.
            port_name (str): The name of the port.

        Returns:
            Port[Module]: The port created from the data of this instance, the port name,
                and the `net_number_map`; the port is already added to the given module.
        """
        direction = Direction.get(self.direction or '')
        msb_first = not bool(self.upto)  # upto=1 represents port[0:7], upto=0/None represents port[7:0]
        params = PortParams(upto=self.upto, offset=self.offset, signed=self.signed)
        p = Port(name=port_name, direction=direction, msb_first=msb_first, parameters=params, module_or_instance=module)
        self._build_connections(net_number_map, module, p)
        self.build_metadata(p)
        return p

    def _build_connections(self, net_number_map: Dict[PositiveInt, WireSegmentPath], module: Module, port: Port[Module]) -> None:
        offset = 0 if not self.offset else self.offset
        if self.bits:
            for i, b in enumerate(self.bits, offset):
                ps = port.create_port_segment(i)
                if isinstance(b, str):
                    ps.change_connection(CONST_MAP_YOSYS2OBJ[b].path)
                elif b in net_number_map:
                    ps.change_connection(net_number_map[b])
                    ws = module.get_from_path(net_number_map[b])
                    ws.add_port_segment(ps)
                else:
                    raise AttributeError(f'No matching wire found for port {port.name} in module {module.name} and net number {b}!')
        else:
            raise AttributeError(f'No bits entry found for port {port.name} in module {module.name}!')


class CellData(NetlistContent):
    hide_name: Literal[0, 1] = 0
    type: Optional[str] = None
    parameters: Optional[Dict[str, str]] = None
    parameter_default_values: Optional[Dict[str, str]] = None
    port_directions: Optional[PortDirections] = None
    connections: Optional[Dict[str, List[BitAlias]]] = None
    _type_replacement_map = {'§_BUF_': '§buf'}

    def clean(self) -> None:
        if self.type:
            self.type = self._clean_str(self.type)
        if self.attributes:
            for k in list(self.attributes):
                self.attributes[self._clean_str(k)] = self._clean_str(self.attributes.pop(k))
        return super().clean()

    @property
    def _new_port_names(self) -> Dict[str, str]:
        if 'adff' in (self.type or ''):  # FF with asyncronous reset
            return {'ARST': 'RST'}
        if 'sdff' in (self.type or ''):  # FF with syncronous reset
            return {'SRST': 'RST'}
        if 'mux' in (self.type or ''):
            return {'A': 'D0', 'B': 'D1'}
        return {}

    @property
    def ports(self) -> Dict[str, Tuple[Direction, List[BitAlias]]]:
        """Reads the `port_directions` and `connections` dictionaries and returns a combined dictionary.

        If a port from `port_directions` is not present in the `connections` dictionary,
        it is assumed to be a placeholder port with no segments (i.e. a width of 0).
        If a port from `connections` is not present in the `port_directions` dictionary,
        the direction is set to `Direction.UNKNOWN`.
        If one of both dictionaries are None, this is applied to all ports from the other
        dictionary, i.e. either every port has no connections, or all directions are UNKNOWN.
        If both dictionaries are None, the returned dictionary is empty.
        """
        p_dict = {}
        dir_dict = self.port_directions or {}
        bit_dict = self.connections or {}
        for pname, direction in dir_dict.items():
            p_dict[pname] = (Direction.get(direction), bit_dict.get(pname, []))
        for pname, bit_list in bit_dict.items():
            if pname not in p_dict:
                p_dict[pname] = (Direction.UNKNOWN, bit_list)
        for old, new in self._new_port_names.items():
            if old in p_dict:
                p_dict[new] = p_dict.pop(old)
        return p_dict

    def build_instance(
        self, module_definitions: Set[str], net_number_map: Dict[PositiveInt, WireSegmentPath], module: Module, inst_name: str
    ) -> Instance:
        """Builds an instance object from the data of this object and the given name and adds it to the given module.

        The `net_number_map` is required to map connection numbers to actual instances from the given module.
        The `module_definition` dictionary contains all modules that are already known. This is required
        to determine if a non-primitive cell is considered a module instance or a blackbox.

        Args:
            module_definitions (Set[str]): A dictionary contains all modules that are already known.
                This is required to determine if a non-primitive cell is considered a module instance or a blackbox.
            net_number_map (Dict[PositiveInt, instanceSegmentPath]): A dictionary mapping connection numbers
                to wire segments from the given module.
            module (Module): The module for which an instance is created.
            inst_name (str): The name of the instance.

        Returns:
            Instance: The instance created from the data of this object, the instance name,
                and the `net_number_map`; the instance is already added to the given module.
        """
        if not self.type:
            raise ValueError(f'Cell type of cell {inst_name!r} is None or not valid!')
        if self.type in self._type_replacement_map:
            self.type = self._type_replacement_map[self.type]

        inst = module.add_instance(self._get_inst(module_definitions, self.type, inst_name))
        self._build_instance_ports(net_number_map, module, inst)
        self._build_parameters(inst)
        self.build_metadata(inst)
        return inst

    def _get_inst(self, module_definitions: Set[str], type_str: str, inst_name: str) -> Instance:
        if type_str[0] == CFG.id_internal and type_str not in module_definitions:
            inst_cls = get(type_str)
            if inst_cls is not None:
                return inst_cls(name=inst_name, is_primitive=True, module=None)  # type:ignore
            LOG.warn(f'No matching gate found for seemingly primitive instance type {type_str}! Creating a blackbox instead...')
        return Instance(name=inst_name, instance_type=type_str, module=None)

    def _build_instance_ports(self, net_number_map: Dict[PositiveInt, WireSegmentPath], module: Module, inst: Instance) -> None:
        for pname, ptuple in self.ports.items():
            direction, bits = ptuple
            p = inst.ports[pname] if pname in inst.ports else Port(name=pname, direction=direction, module_or_instance=inst)
            p.segments.clear()  # Clear any existing segments, as we are rebuilding them from the Yosys data
            for i, b in enumerate(bits):
                b_int = self._try_get_int(b)
                if b_int in net_number_map:
                    w_path = net_number_map[int(b_int)]
                    inst.connect(pname, w_path, index=i)
                    w_seg = module.get_from_path(w_path)
                    w_seg.add_port_segment(p[i])
                elif b in CONST_MAP_YOSYS2OBJ.keys() and isinstance(b, str):
                    inst.connect(pname, CONST_MAP_YOSYS2OBJ[b].path, index=i)
                else:
                    raise AttributeError(f'No matching wire found for port {pname} of instance {inst.raw_path} and net number {b}!')

    def _build_parameters(self, inst: Instance) -> None:
        if self.parameters:
            for attr_name, attr_val in self.parameters.items():
                if 'SIGNED' in attr_name:
                    inst.parameters[attr_name] = bool(int(attr_val, 2))
                else:
                    inst.parameters[attr_name] = self._try_get_int(attr_val)
        self._update_all_param_types(inst)

    def _update_all_param_types(self, inst: Instance) -> None:
        self._update_param_type(inst, 'CLK_POLARITY', 'CLK_POLARITY', Signal.get)
        self._update_param_type(inst, 'ARST_VALUE', 'RST_VALUE', int, delete_old=True)
        self._update_param_type(inst, 'ARST_POLARITY', 'RST_POLARITY', Signal.get, delete_old=True)
        self._update_param_type(inst, 'SRST_VALUE', 'RST_VALUE', int, delete_old=True)
        self._update_param_type(inst, 'SRST_POLARITY', 'RST_POLARITY', Signal.get, delete_old=True)
        self._update_param_type(inst, 'CLR_POLARITY', 'CLR_POLARITY', Signal.get)
        self._update_param_type(inst, 'SET_POLARITY', 'SET_POLARITY', Signal.get)
        self._update_param_type(inst, 'EN_POLARITY', 'EN_POLARITY', Signal.get)

    def _update_param_type(
        self,
        inst: Instance,
        old_param_key: str,
        new_param_key: str,
        value_fnc: Callable[[Union[str, int]], object],
        delete_old: bool = False,
    ) -> None:
        if self.parameters:
            if old_param_key in self.parameters:
                val_int = self._try_get_int(self.parameters[old_param_key])
                setattr(inst.parameters, new_param_key, value_fnc(val_int))
                if delete_old and hasattr(inst.parameters, old_param_key):
                    delattr(inst.parameters, old_param_key)


class WireData(NetlistContent):
    hide_name: Literal[0, 1] = 0
    bits: Optional[List[BitAlias]] = None
    upto: Optional[int] = None
    offset: Optional[int] = None
    signed: Optional[int] = None

    def clean(self) -> None:
        if self.attributes:
            for k in list(self.attributes):
                self.attributes[self._clean_str(k)] = self._clean_str(self.attributes.pop(k))
        return super().clean()

    def build_wire(self, net_number_map: Dict[PositiveInt, WireSegmentPath], module: Module, wire_name: str) -> Wire:
        """Builds a wire object from the data of this object and the given name and adds it to the given module.

        The `net_number_map` is required to map connection numbers to actual wires from the given module.

        Args:
            net_number_map (Dict[PositiveInt, WireSegmentPath]): A dictionary mapping connection numbers
                to wire segments from the given module.
            module (Module): The module for which a wire is created.
            wire_name (str): The name of the wire.

        Returns:
            Wire: The wire created from the data of this instance, the wire name,
                and the `net_number_map`; the wire is already added to the given module.
        """
        msb_first = not bool(self.upto)  # upto=1 represents wire[0:7], upto=0/None represents wire[7:0]
        params = WireParams(signed=self.signed)
        w = module.add_wire(Wire(name=wire_name, msb_first=msb_first, module=module, parameters=params))
        self._build_connections(net_number_map, module, w)
        self.build_metadata(w)
        return w

    def _build_connections(self, net_number_map: Dict[PositiveInt, WireSegmentPath], module: Module, wire: Wire) -> None:
        offset = 0 if not self.offset else self.offset
        if self.bits:
            for seg_i, b in enumerate(self.bits, offset):
                if isinstance(b, str):
                    wire.segments.add(seg_i, CONST_MAP_YOSYS2OBJ[b])
                else:
                    net_number_map[b] = WireSegmentPath(raw=f'{wire.raw_path}.{seg_i}')
                    wire.create_wire_segment(seg_i)
        else:
            raise AttributeError(f'No bits entry found for wire {wire.name} in module {module.name}!')


class YosysModule(NetlistContent):
    parameter_default_values: Optional[Dict[str, str]] = None
    ports: Optional[Dict[str, PortData]] = None
    cells: Optional[Dict[str, CellData]] = None
    netnames: Optional[Dict[str, WireData]] = None

    def clean(self) -> None:
        if self.attributes:
            for k in list(self.attributes):
                self.attributes[self._clean_str(k)] = self._clean_str(self.attributes.pop(k))
        if self.ports:
            for k, p in list(self.ports.items()):
                self.ports[self._clean_str(k)] = self.ports.pop(k)
                p.clean()
        if self.cells:
            for k, c in list(self.cells.items()):
                self.cells[self._clean_str(k)] = self.cells.pop(k)
                c.clean()
        if self.netnames:
            for k, n in list(self.netnames.items()):
                self.netnames[self._clean_str(k)] = self.netnames.pop(k)
                n.clean()
        return super().clean()

    def replace(self, old: str, new: str) -> None:
        if self.attributes:
            for k in list(self.attributes):
                self.attributes[k.replace(old, new)] = self.attributes.pop(k).replace(old, new)
        if self.ports:
            for k, p in list(self.ports.items()):
                self.ports[k.replace(old, new)] = self.ports.pop(k)
                p.replace(old, new)
        if self.cells:
            for k, c in list(self.cells.items()):
                self.cells[k.replace(old, new)] = self.cells.pop(k)
                if c.type:
                    c.type = c.type.replace(old, new)
                c.replace(old, new)
        if self.netnames:
            for k, n in list(self.netnames.items()):
                self.netnames[k.replace(old, new)] = self.netnames.pop(k)
                n.replace(old, new)

    def build_parameters(self, module: Module) -> None:
        if self.parameter_default_values:
            for attr_name, attr_val in self.parameter_default_values.items():
                module.parameters[attr_name] = self._try_get_int(attr_val)


class YosysData(NetlistContent):
    creator: Optional[str] = None
    modules: Optional[Dict[str, YosysModule]] = None

    def clean(self) -> None:
        self._shorten_yosys_name()
        if self.creator:
            self.creator = self._clean_str(self.creator)
        if self.modules:
            for k, v in list(self.modules.items()):
                self.modules[self._clean_str(k)] = self.modules.pop(k)
                v.clean()
        return super().clean()

    def replace(self, old: str, new: str) -> None:
        if self.creator:
            self.creator = self.creator.replace(old, new)
        if self.modules:
            for k, m in list(self.modules.items()):
                self.modules[k.replace(old, new)] = self.modules.pop(k)
                m.replace(old, new)

    def _shorten_yosys_name(self) -> None:
        """Shorten Yosys-style name deterministically while preventing collisions.

        In the original module dict, cell names may be long and weird names, containing the full path
        to the source file, generated by Yosys, e.g. "$and$/path/to/file.v:420$69". This method simplifies
        these names, so that it is shortened to e.g. "file§420§69".
        """
        # Pattern: $type$path:line$char
        if not self.modules:
            return
        for module in self.modules.values():
            mapping: Dict[str, str] = {}
            if module.cells:
                for cellname in list(module.cells.keys()):
                    m = re.match(r'^\$([^$]+)\$(.+?):(\d+)\$(\d+)$', cellname)
                    if m:
                        ctype, path, lno, ch = m.groups()
                    else:
                        ctype, path, lno, ch = None, cellname, None, None

                    # Put together to a readable string again: basename (+line if available)
                    basename = os.path.basename(path)
                    hint = basename if basename else 'unnamed'
                    if lno and ch:
                        hint = f'{hint}{CFG.id_internal}{lno}{CFG.id_internal}{ch}'
                    short = f'{ctype}{CFG.id_internal}{hint}' if ctype else hint
                    counter = 0
                    while short in mapping and mapping[short] != cellname:
                        # Collision with a different name
                        counter += 1
                        short = f'{short}_{counter}'
                    # Preserve cell name mapping for this module
                    mapping[short] = cellname
                    module.cells[short] = module.cells.pop(cellname)


AllYosysTypes = Union[YosysData, CellData, YosysModule, WireData, PortData]

ModuleName = str
NetNumber = PositiveInt
NewModuleName = str
OldModuleName = str

NetNumberMappingDict = Dict[ModuleName, Dict[PositiveInt, WireSegmentPath]]
ModuleNameMapping = Dict[NewModuleName, OldModuleName]


def __getattr__(name: str) -> object:
    new_class_name_map = {'PortAttributes': PortData, 'YosysCell': CellData, 'Netnames': WireData, 'YosysPortDirections': PortDirections}
    if name in new_class_name_map:
        new = new_class_name_map[name]
        warnings.warn(
            f'The {name!r} class is deprecated and will be removed in v1.0.0. Use {new.__name__!r} instead.',
            DeprecationWarning,
            stacklevel=2,  # Ensures the warning points to the user's code, not this line
        )
        return new
    # Standard behavior for missing attributes
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
