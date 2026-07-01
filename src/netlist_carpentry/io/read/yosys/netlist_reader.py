"""Module handling the reading of a Yosys-generated JSON netlist and transformation into corresponding Python objects."""
# mypy: disable-error-code="unreachable"

import json
import os
import re
from pathlib import Path
from time import time
from typing import Callable, Dict, List, Optional, Set, Union, overload

from tqdm import tqdm

from netlist_carpentry import CFG, LOG, Circuit, Direction, Instance, Module, Port, Signal, Wire
from netlist_carpentry.core.netlist_elements.element_path import WireSegmentPath
from netlist_carpentry.core.netlist_elements.netlist_element import NetlistElement
from netlist_carpentry.core.netlist_elements.wire_segment import CONST_MAP_YOSYS2OBJ, WireSegment
from netlist_carpentry.io.read.abstract_reader import AbstractReader
from netlist_carpentry.io.read.yosys.netlist_types import (
    AllYosysTypes,
    BitAlias,
    ModuleNameMapping,
    NetNumberMappingDict,
    YosysCell,
    YosysData,
    YosysModule,
    YosysPortDirections,
)
from netlist_carpentry.utils.gate_lib import DFF, get
from netlist_carpentry.utils.gate_mixins import EnableMixinProtocol, RstMixin, SRMixin


class YosysNetlistReader(AbstractReader):
    def __init__(self, path: Union[str, Path]):
        super().__init__(path)
        self.net_number_mapping: NetNumberMappingDict = {}

        self._module_name_mapping: ModuleNameMapping = {}
        self._module_definitions: Set[str] = set()
        self._module_instantiations: Set[str] = set()
        self._wire_cnt = 0

        # Remains None until the circuit is created via the transform_to_circuit method
        self.circuit: Optional[Circuit] = None

    @property
    def module_name_mapping(self) -> ModuleNameMapping:
        """The mapping from original module names to normalized module names."""
        return self._module_name_mapping

    @property
    def module_definitions(self) -> Set[str]:
        """The set of module definitions found in the netlist."""
        return self._module_definitions

    @property
    def module_instantiations(self) -> Set[str]:
        """The set of module instantiations found in the netlist."""
        return self._module_instantiations

    @property
    def undefined_modules(self) -> Set[str]:
        """
        Return a set of module names that are instantiated but not defined in the netlist.

        This set indicates submodule instantiations, where no definition is present.
        These instances will be treated as black-box cells, since their implementation
        remains unknown.
        """
        return self.module_instantiations.difference(self.module_definitions)

    @property
    def uninstantiated_modules(self) -> Set[str]:
        """Return a set of module names that are defined but not instantiated in the netlist.

        This set indicates module definitions that are never used anywhere.
        These modules might be unnecessary.
        """
        return self.module_definitions.difference(self.module_instantiations)

    @property
    def module_definitions_and_instances_match(self) -> bool:
        # Check if there are uninstantiated modules (besides the top module)
        top_name: Set[str] = {self.circuit.top.name} if self.circuit is not None and self.circuit.top is not None else set()
        uninstantiated_modules = self.uninstantiated_modules.difference(top_name)
        if uninstantiated_modules:
            diff = self.uninstantiated_modules
            LOG.warn(f'Found modules defined but not instantiated: {diff}')
        # Check if there are undefined modules
        if self.undefined_modules:
            diff = self.undefined_modules
            LOG.error(f'Found modules instantiated but not defined: {diff}')
        return not self.undefined_modules and not uninstantiated_modules

    def read(self) -> YosysData:
        with open(self.path) as f:
            netlist_dict: YosysData = json.loads(f.read())
            return self._preprocess_dict(netlist_dict)

    def _preprocess_dict(self, nl_dict: YosysData) -> YosysData:
        LOG.debug(f"Replacing all special characters with their internal representation, which is currently set to '{CFG.id_internal}'...")
        start = time()
        self._shorten_yosys_name(nl_dict['modules'])
        nl_dict['modules'] = self._clean_dict(nl_dict['modules'])  # type:ignore
        LOG.debug(f'Replaced all special characters with their internal representation in {time() - start:.2f}s.')

        for mname in nl_dict['modules']:
            simple_name = self.simplify_module_name(mname)
            if simple_name != mname:
                LOG.debug(f"Simplifying module name '{mname}' to '{simple_name}'...")
                nl_dict['modules'] = self._replace_in_module_dict(nl_dict['modules'], mname, simple_name)  # type:ignore
                LOG.debug(f"Simplified module name '{mname}' to '{simple_name}'!")
        return nl_dict

    def _shorten_yosys_name(self, modules_dict: Dict[str, YosysModule]) -> None:
        """Shorten Yosys-style name deterministically while preventing collisions.

        Args:
            modules_dict (Dict[str, YosysModule]): Original module dict, where cell names may be long and weird names,
                containing the full path to the source file, generated by Yosys, e.g. "$and$/path/to/file.v:420$69"
        """
        # Pattern: $type$path:line$char
        for module in modules_dict.values():
            mapping: Dict[str, str] = {}
            if 'cells' in module:
                for cellname in list(module['cells'].keys()):
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
                    module['cells'][short] = module['cells'].pop(cellname)

    def _replace_in_module_dict(self, inner_dict: Dict[str, dict], old_val: str, new_val: str) -> Dict[str, dict]:  # type:ignore
        """Recursively replace all occurrences of `old_val` with `new_val` in dictionary keys and values."""
        if isinstance(inner_dict, dict):  # type:ignore # If it's a dictionary, process keys and values
            return {k.replace(old_val, new_val): self._replace_in_module_dict(v, old_val, new_val) for k, v in inner_dict.items()}  # type:ignore
        elif isinstance(inner_dict, list):  # If it's a list, process each item
            return [self._replace_in_module_dict(item, old_val, new_val) for item in inner_dict]
        elif isinstance(inner_dict, str):  # If it's a string, replace old_val with new_val
            return inner_dict.replace(old_val, new_val)
        else:
            return inner_dict  # Return unchanged for other data types

    def _clean_dict(self, nl_dict: Dict[str, object]) -> Dict[str, object]:
        if isinstance(nl_dict, dict):
            new_dict: Dict[str, object] = {}
            for k, v in nl_dict.items():
                clean_k = self._clean_dict_substitute_str(k)
                # Resolve collisions
                original = clean_k
                counter = 1
                while clean_k in new_dict:
                    clean_k = f'{original}_{counter}'
                    counter += 1
                new_dict[clean_k] = self._clean_dict_element(v)
            return new_dict

    @overload
    def _clean_dict_element(self, element: List[str]) -> List[str]: ...
    @overload
    def _clean_dict_element(self, element: str) -> str: ...
    @overload
    def _clean_dict_element(self, element: object) -> object: ...

    def _clean_dict_element(self, element: object) -> object:
        if isinstance(element, str):
            return self._clean_dict_substitute_str(element)
        if isinstance(element, list):
            return [self._clean_dict_element(x) for x in element]
        if isinstance(element, dict):
            return self._clean_dict(element)
        return element

    def _clean_dict_substitute_str(self, dict_entry: str) -> str:
        return re.sub(r'[^A-Za-z0-9_]', CFG.id_internal, dict_entry)

    def simplify_module_name(self, module_name: str) -> str:
        new_m = module_name
        if CFG.id_internal in new_m:
            # Main issue is with parametrized module names, indicated by "$paramod\" by Yosys
            if f'{CFG.id_internal}paramod{CFG.id_internal}' in module_name:
                module_names = module_name.replace(f'{CFG.id_internal}paramod{CFG.id_internal}', '').split(CFG.id_internal)
                new_m = ''
                for idx, mseg in enumerate(module_names):
                    if all(ch in '01' for ch in mseg) and '32' in module_names[idx - 1]:
                        new_m = new_m[: -len(module_names[idx - 1])]
                        new_m += str(int(mseg, 2))
                    else:
                        new_m += CFG.id_internal + mseg
            else:
                new_m = re.sub(r'\W', CFG.id_internal, new_m)
        if new_m not in self.module_name_mapping:
            self._module_name_mapping[new_m] = module_name
            return new_m
        raise KeyError(
            f'Simplified module name "{module_name}" to "{new_m}", but this name is already associated with module "{self.module_name_mapping[new_m]}"!'
        )

    def transform_to_circuit(self, name: Optional[str] = None) -> Circuit:
        LOG.debug(f'Reading Yosys netlist from file {self.path}...')
        start = time()
        modules_dict = self.read()
        LOG.debug(f'Read Yosys netlist from file {self.path} in {round(time() - start, 2)}s!')
        if name is None:
            name = str(self.path.stem)
        self.circuit = Circuit(name=name)

        return self._populate_circuit(modules_dict['modules'], self.circuit)

    def _populate_circuit(self, modules_dict: Dict[str, YosysModule], circuit: Circuit) -> Circuit:
        self._module_definitions.update(modules_dict.keys())
        for mname in modules_dict:
            s = time()
            LOG.debug(f'Building module {mname}...')
            circuit.add_module(self._populate_module(Module(name=mname), modules_dict[mname]))
            # TODO check for multiple top modules!
            if 'attributes' in modules_dict[mname] and 'top' in modules_dict[mname]['attributes']:
                LOG.debug(f'Setting module {mname} as new top module as specified in the netlist!')
                circuit.set_top(mname)
            LOG.debug(f'Built module {mname} in {round(time() - s, 2)}s!')
        return circuit

    def _populate_module(self, module: Module, module_dict: YosysModule) -> Module:
        self._build_wires(module, module_dict)
        self._build_ports(module, module_dict)
        self._build_instances(module, module_dict)
        self._build_metadata(module, module_dict)
        self._build_module_parameters(module, module_dict)

        return module

    def _build_wires(self, module: Module, module_dict: YosysModule) -> None:
        self.net_number_mapping[module.name] = {}
        if 'netnames' in module_dict:
            LOG.debug(f'Building {len(module_dict["netnames"])} wires...')
            start = time()
            for wire_name, wire_data in tqdm(module_dict['netnames'].items(), desc='Wire building progress', leave=False):
                w_path = f'{module.name}.{wire_name}'
                msb_first = 'upto' not in wire_data
                w = Wire(name=wire_name, msb_first=msb_first, module=module)
                self._build_metadata(w, wire_data)
                self._build_parameters(w, wire_data)
                w.parameters['signed'] = wire_data['signed'] if 'signed' in wire_data else 0
                if 'bits' in wire_data:
                    offset = 0 if 'offset' not in wire_data or wire_data['offset'] is None else wire_data['offset']
                    for seg_i, b in enumerate(wire_data['bits'], offset):
                        path = f'{w_path}.{seg_i}'
                        if isinstance(b, str):
                            w.segments.add(seg_i, CONST_MAP_YOSYS2OBJ[b])
                        else:
                            self.net_number_mapping[module.name][b] = WireSegmentPath(raw=path)
                            w.create_wire_segment(seg_i)
                else:
                    raise AttributeError(f'No bits entry found for wire {wire_name} in module {module.name}!')

                module.add_wire(w)
            LOG.debug(f'Built {len(module_dict["netnames"])} wires in {time() - start:.2f}s.')

    def _build_ports(self, module: Module, module_dict: YosysModule) -> None:
        if 'ports' in module_dict:
            LOG.debug(f'Building {len(module_dict["ports"])} module ports...')
            start = time()
            for port_name, port_data in tqdm(module_dict['ports'].items(), desc='Port building progress', leave=False):
                direction = Direction.get(port_data['direction']) if 'direction' in port_data else Direction.UNKNOWN
                msb_first = 'upto' not in port_data or port_data['upto'] != 1
                p = Port(name=port_name, direction=direction, msb_first=msb_first, module_or_instance=module)
                module.add_port(p)
                self._build_metadata(p, port_data)
                self._build_parameters(p, port_data)
                p.parameters['signed'] = port_data['signed'] if 'signed' in port_data else 0
                if 'bits' in port_data:
                    offset = 0 if 'offset' not in port_data or port_data['offset'] is None else port_data['offset']
                    for i, b in enumerate(port_data['bits'], offset):
                        ps = p.create_port_segment(i)
                        if isinstance(b, str):
                            ps.change_connection(CONST_MAP_YOSYS2OBJ[b].path)
                        elif b in self.net_number_mapping[module.name]:
                            ws_path = self.net_number_mapping[module.name][b]
                            ps.change_connection(ws_path)
                            ws: WireSegment = module.get_from_path(ws_path)
                            ws.add_port_segment(ps)
                        else:
                            err_msg = f'No matching wire found for port {port_name} in module {module.name} and net number {b}!'
                            debug_msg = f'The netnumber-to-wire dictionary of this module is {self.net_number_mapping[module.name]}'
                            LOG.debug(err_msg)
                            LOG.debug(debug_msg)
                            raise AttributeError(err_msg)
                else:
                    raise AttributeError(f'No bits entry found for port {port_name} in module {module.name}!')
            LOG.debug(f'Built {len(module_dict["ports"])} module ports in {time() - start:.2f}s.')

    def _build_instances(self, module: Module, module_dict: YosysModule) -> None:
        if 'cells' in module_dict:
            LOG.debug(f'Building {len(module_dict["cells"])} instances...')
            start = time()
            for inst_name, inst_data in tqdm(module_dict['cells'].items(), desc='Instance building progress', leave=False):
                self._build_single_instance(module, inst_name, inst_data)
            LOG.debug(f'Built {len(module_dict["cells"])} instances in {time() - start:.2f}s.')

    def _build_single_instance(self, module: Module, inst_name: str, inst_data: YosysCell) -> None:
        # Replace illegal characters with internal identifer to indicate special characters
        # TODO when writing to Verilog, put original characters back?
        inst_name = inst_name.replace('.', CFG.id_internal).replace(':', CFG.id_internal)
        type_str = inst_data['type'].replace('$', CFG.id_internal)
        if type_str in TYPE_REPLACEMENT_MAP:
            type_str = TYPE_REPLACEMENT_MAP[type_str]
        if self._dict_must_be_prepared(type_str):
            self._prepare_dict(type_str, inst_data)

        inst = self._get_inst(type_str, inst_name)
        inst.module = module
        self._build_metadata(inst, inst_data)
        self._build_parameters(inst, inst_data)
        self._instance_post_processing(inst, inst_data)
        self._build_instance_ports(module, inst, inst_data)
        module.add_instance(inst)

    def _build_instance_ports(self, module: Module, inst: Instance, instance_data_dict: YosysCell) -> None:
        for port_name, port_connection in instance_data_dict['connections'].items():
            # Default ports in primitives from gate library have placeholder segments
            # They must be removed before assigning read data
            if port_name in inst.ports:
                inst.ports[port_name].segments.clear()
            if 'port_directions' in instance_data_dict:
                port_direction = self._build_instance_ports_direction(instance_data_dict['port_directions'], port_name)
            else:
                LOG.debug(f'Instance {inst.raw_path} has no directions and will thus be treated as a black-box!')
                port_direction = Direction.UNKNOWN
            self._build_instance_ports_connections(module, inst, port_name, port_connection, port_direction)

    def _build_instance_ports_direction(self, pdirs: YosysPortDirections, pname: str) -> Direction:
        return Direction.UNKNOWN if pname not in pdirs else Direction.get(pdirs[pname])

    def _build_instance_ports_connections(
        self, module: Module, inst: Instance, port_name: str, connections: List[BitAlias], directions: Direction
    ) -> None:
        for i, b in enumerate(connections):
            b_int = self._try_get_int(b)
            if b_int in self.net_number_mapping[module.name]:
                w_path = self.net_number_mapping[module.name][int(b_int)]
                inst.connect(port_name, w_path, directions, i)
                w_seg: WireSegment = module.get_from_path(w_path)
                w_seg.add_port_segment(inst.ports[port_name][i])
            elif b in CONST_MAP_YOSYS2OBJ.keys() and isinstance(b, str):
                inst.connect(port_name, CONST_MAP_YOSYS2OBJ[b].path, directions, i)
            else:
                err_msg = f'No matching wire found for port {port_name} of instance {inst.raw_path} and net number {b}!'
                debug_msg = f'The netnumber-to-wire dictionary of the module is {self.net_number_mapping[module.name]}'
                LOG.debug(err_msg)
                LOG.debug(debug_msg)
                raise AttributeError(err_msg)

    def _build_metadata(self, netlist_element: NetlistElement, dict: Dict[str, Dict[str, str]]) -> None:
        if 'attributes' in dict:
            netlist_element.metadata.add_category('yosys')
            for attr_name, attr_val in dict['attributes'].items():
                netlist_element.metadata.yosys[attr_name] = self._try_get_int(attr_val)

    def _build_module_parameters(self, module: Module, module_dict: YosysModule) -> None:
        if 'parameter_default_values' in module_dict:
            module_dict['parameters'] = module_dict.pop('parameter_default_values')
        self._build_parameters(module, module_dict)

    def _build_parameters(self, dict_holder: NetlistElement, module_dict: AllYosysTypes) -> None:
        if 'parameters' in module_dict:
            for attr_name, attr_val in module_dict['parameters'].items():  # type:ignore
                if 'SIGNED' in attr_name:  # type: ignore[misc]
                    dict_holder.parameters[attr_name] = bool(int(attr_val, 2))  # type: ignore[misc]
                else:
                    dict_holder.parameters[attr_name] = self._try_get_int(attr_val)  # type:ignore

    def _try_get_int(self, str_val: Union[str, int]) -> Union[int, str]:
        if isinstance(str_val, int):
            return str_val
        if all(c == '0' or c == '1' for c in str_val) and str_val:
            return int(str_val, 2)
        return str_val

    def _get_inst(self, type_str: str, inst_name: str) -> Instance:
        is_primitive = type_str[0] == CFG.id_internal
        if is_primitive and type_str not in self.module_definitions:
            inst_cls = get(type_str)
            if inst_cls is not None:
                return inst_cls(name=inst_name, is_primitive=True, module=None)  # type:ignore
            LOG.warn(f'No matching gate found for seemingly primitive instance type {type_str}! Creating a blackbox instead...')
        self._module_instantiations.add(type_str)
        return Instance(name=inst_name, instance_type=type_str, module=None)

    def _dict_must_be_prepared(self, inst_type: str) -> int:
        return CFG.id_internal in inst_type and ('dff' in inst_type or 'mux' in inst_type)

    def _prepare_dict(self, inst_type: str, inst_data: YosysCell) -> None:
        if 'dff' in inst_type:
            self._prepare_dff_dict(inst_type, inst_data)
        if 'mux' in inst_type:
            self._prepare_mux_dict(inst_type, inst_data)

    def _prepare_dff_dict(self, ff_type: str, ff_dict: YosysCell) -> None:
        if 'adff' in ff_type:  # FF with asyncronous reset
            ff_dict['port_directions']['RST'] = ff_dict['port_directions'].pop('ARST')
            ff_dict['connections']['RST'] = ff_dict['connections'].pop('ARST')
        if 'sdff' in ff_type:  # FF with syncronous reset
            ff_dict['port_directions']['RST'] = ff_dict['port_directions'].pop('SRST')
            ff_dict['connections']['RST'] = ff_dict['connections'].pop('SRST')

    def _prepare_mux_dict(self, mux_type: str, mux_data: YosysCell) -> None:
        mux_data['port_directions']['D0'] = mux_data['port_directions'].pop('A')
        mux_data['port_directions']['D1'] = mux_data['port_directions'].pop('B')
        mux_data['connections']['D0'] = mux_data['connections'].pop('A')
        mux_data['connections']['D1'] = mux_data['connections'].pop('B')

    def _instance_post_processing(self, inst: Instance, inst_data: YosysCell) -> None:
        if isinstance(inst, DFF):
            self._instance_param_fix(inst, inst_data, 'CLK_POLARITY', 'CLK_POLARITY', Signal.get)
        if isinstance(inst, RstMixin):
            self._instance_param_fix(inst, inst_data, 'ARST_VALUE', 'RST_VALUE', int, delete_old=True)
            self._instance_param_fix(inst, inst_data, 'ARST_POLARITY', 'RST_POLARITY', Signal.get, delete_old=True)
            self._instance_param_fix(inst, inst_data, 'SRST_VALUE', 'RST_VALUE', int, delete_old=True)
            self._instance_param_fix(inst, inst_data, 'SRST_POLARITY', 'RST_POLARITY', Signal.get, delete_old=True)
        if isinstance(inst, SRMixin):
            self._instance_param_fix(inst, inst_data, 'CLR_POLARITY', 'CLR_POLARITY', Signal.get)
            self._instance_param_fix(inst, inst_data, 'SET_POLARITY', 'SET_POLARITY', Signal.get)
        if isinstance(inst, EnableMixinProtocol):
            self._instance_param_fix(inst, inst_data, 'EN_POLARITY', 'EN_POLARITY', Signal.get)

    def _instance_param_fix(
        self,
        inst: Instance,
        inst_data: YosysCell,
        old_param_key: str,
        new_param_key: str,
        value_fnc: Callable[[Union[str, int]], object],
        delete_old: bool = False,
    ) -> None:
        if old_param_key in inst_data['parameters']:
            rst_pol = self._try_get_int(inst_data['parameters'][old_param_key])
            setattr(inst.parameters, new_param_key, value_fnc(rst_pol))
            if delete_old and hasattr(inst.parameters, old_param_key):
                delattr(inst.parameters, old_param_key)


TYPE_REPLACEMENT_MAP = {
    '§_BUF_': '§buf',
}
