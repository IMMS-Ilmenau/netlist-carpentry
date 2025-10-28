import json
import re
from pathlib import Path
from time import time
from typing import Dict, List, Optional, Set, Tuple, Union

from tqdm import tqdm

from netlist_carpentry import CFG, LOG
from netlist_carpentry.api.read._abstract_reader import _AbstractReader
from netlist_carpentry.api.read.yosys_netlist_types import AllYosysTypes, BitAlias, YosysCell, YosysData, YosysModule
from netlist_carpentry.core.circuit import Circuit
from netlist_carpentry.core.netlist_elements.element_path import WireSegmentPath
from netlist_carpentry.core.netlist_elements.instance import Instance
from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.core.netlist_elements.netlist_element import NetlistElement
from netlist_carpentry.core.netlist_elements.port import Port
from netlist_carpentry.core.netlist_elements.wire import Wire
from netlist_carpentry.core.netlist_elements.wire_segment import CONST_MAP_YOSYS2OBJ, WireSegment
from netlist_carpentry.core.port_direction import PortDirection
from netlist_carpentry.core.signal import Signal
from netlist_carpentry.utils._gate_lib_base import LibUtils
from netlist_carpentry.utils.gate_lib import DFF, DLatch, get


class YosysNetlistReader(_AbstractReader):
    def __init__(self, path: Union[str, Path]):
        super().__init__(path)
        self.net_number_mapping: Dict[str, Dict[int, WireSegmentPath]] = {}

        self._module_name_mapping: Dict[str, str] = {}
        self._port_name_mapping: Dict[str, List[Tuple[str, str]]] = {}
        self._instance_name_mapping: Dict[str, Dict[str, str]] = {}
        self._wire_name_mapping: Dict[str, Dict[str, str]] = {}
        self._module_definitions: Set[str] = set()
        self._module_instantiations: Set[str] = set()
        self._wire_cnt = 0

        # Remains None until the circuit is created via the transform_to_circuit method
        self.circuit: Optional[Circuit] = None

    @property
    def module_name_mapping(self) -> Dict[str, str]:
        """The mapping from original module names to normalized module names."""
        return self._module_name_mapping

    @property
    def port_name_mapping(self) -> Dict[str, List[Tuple[str, str]]]:
        """The mapping from original port names to normalized port name tuples."""
        return self._port_name_mapping

    @property
    def instance_name_mapping(self) -> Dict[str, Dict[str, str]]:
        """The mapping from original instance names to normalized instance names."""
        return self._instance_name_mapping

    @property
    def wire_name_mapping(self) -> Dict[str, Dict[str, str]]:
        """The mapping from original wire names to normalized wire names."""
        return self._wire_name_mapping

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
            LOG.error(f'Found modules defined but not instantiated: {diff}')
        return not self.undefined_modules and not uninstantiated_modules

    def read(self) -> YosysData:
        with open(self.path) as f:
            netlist_dict: YosysData = json.loads(f.read())
            if CFG.simplify_escaped_identifiers:
                return self._preprocess_dict(netlist_dict)
            return netlist_dict

    def _preprocess_dict(self, nl_dict: YosysData) -> YosysData:
        LOG.debug(f"Replacing all special characters with their internal representation, which is currently set to '{CFG.id_internal}'...")
        start = time()
        nl_dict['modules'] = self._replace_in_module_dict(nl_dict['modules'], '$', CFG.id_internal)  # type:ignore
        LOG.debug(f'Replaced all special characters with their internal representation in {time() - start:.2f}s.')

        for mname in nl_dict['modules']:
            mdict: YosysModule = nl_dict['modules'][mname]
            LOG.debug(f"Preparing dictionary of module '{mname}'...")
            LOG.debug('Fixing net names...')
            start = time()
            if 'netnames' in mdict:
                new_netnames = {}
                for w in tqdm(mdict['netnames'], desc='Net preprocessing progress'):
                    new_wire_name = self.simplify_wire_name(mname, w)
                    new_netnames[new_wire_name] = mdict['netnames'][w]
                mdict['netnames'] = new_netnames
            LOG.debug(f'Fixed net names in {time() - start:.2f}s.')
            simple_name = self.simplify_module_name(mname)
            if simple_name != mname:
                nl_dict['modules'] = self._replace_in_module_dict(nl_dict['modules'], mname, simple_name)  # type:ignore
            LOG.debug(f"Prepared dictionary of module '{mname}' in {time() - start:.2f}s.")
        return nl_dict

    def _replace_in_module_dict(self, inner_dict: Dict[str, dict], old_val: str, new_val: str) -> Dict[str, dict]:  # type:ignore
        """Recursively replace all occurrences of `old_val` with `new_val` in dictionary keys and values."""
        if isinstance(inner_dict, dict):  # type:ignore # If it's a dictionary, process keys and values
            return {k.replace(old_val, new_val): self._replace_in_module_dict(v, old_val, new_val) for k, v in inner_dict.items()}  # type:ignore
        elif isinstance(inner_dict, list):  # type:ignore # If it's a list, process each item
            return [self._replace_in_module_dict(item, old_val, new_val) for item in inner_dict]
        elif isinstance(inner_dict, str):  # If it's a string, replace old_val with new_val
            return inner_dict.replace(old_val, new_val)
        else:
            return inner_dict  # Return unchanged for other data types

    def simplify_module_name(self, module_name: str) -> str:
        new_m = module_name
        if not module_name.isidentifier():
            # Main issue is with parametrized module names, indicated by "$paramod\" by Yosys
            if 'paramod\\' in module_name:
                module_names = module_name.replace('paramod\\', '').split('\\')
                new_m = ''
                for mseg in module_names:
                    if '=' in mseg:
                        paramname, paramvalue = mseg.split('=')
                        paramvalue = int(paramvalue.split("'")[1], 2)  # type:ignore
                        new_m += f'{CFG.id_internal}{paramname}{paramvalue}'
                    else:
                        new_m += mseg
            else:
                new_m = re.sub(r'\W', CFG.id_internal, new_m)
        if new_m not in self.module_name_mapping:
            self._module_name_mapping[new_m] = module_name
            return new_m
        raise KeyError(
            f'Simplified module name "{module_name}" to "{new_m}", but this name is already associated with module "{self.module_name_mapping[new_m]}"!'
        )

    def simplify_port_name(self, port_name: str, element_path: str) -> str:
        new_p = port_name
        if not port_name.isidentifier():
            new_p = re.sub(r'\W', CFG.id_internal, new_p)
        if new_p[0].isdigit():
            new_p = CFG.id_internal + new_p
        if new_p not in self.port_name_mapping:
            self._port_name_mapping[new_p] = []
        self._port_name_mapping[new_p].append((port_name, element_path))
        return new_p

    def simplify_instance_name(self, module_name: str, instance_name: str) -> str:
        new_i = instance_name
        if not instance_name.isidentifier():
            new_i = re.sub(r'\W', CFG.id_internal, new_i)
        if new_i[0].isdigit():
            new_i = CFG.id_internal + new_i
        if module_name not in self.instance_name_mapping:
            self._instance_name_mapping[module_name] = {}
        if new_i not in self._instance_name_mapping[module_name]:
            self._instance_name_mapping[module_name][new_i] = instance_name
            return new_i
        raise KeyError(
            f'Simplified instance name "{instance_name}" to "{new_i}" in module {module_name}, but this name is already associated with instance "{self.instance_name_mapping[new_i]}"!'
        )

    def simplify_wire_name(self, module_name: str, wire_name: str) -> str:
        new_w = wire_name
        if not wire_name.isidentifier():
            new_w = re.sub(r'\W', CFG.id_internal, new_w)
        if new_w[0].isdigit():
            new_w = CFG.id_internal + new_w
        if module_name not in self.wire_name_mapping:
            self._wire_name_mapping[module_name] = {}
        if new_w not in self._wire_name_mapping[module_name]:
            self._wire_name_mapping[module_name][new_w] = wire_name
            return new_w
        raise KeyError(
            f'Simplified instance name "{wire_name}" to "{new_w}" in module {module_name}, but this name is already associated with instance "{self.wire_name_mapping[new_w]}"!'
        )

    def transform_to_circuit(self, name: str = '') -> Circuit:
        LOG.info(f'Reading Yosys netlist from file {self.path}...')
        start = time()
        modules_dict = self.read()
        LOG.info(f'Read Yosys netlist from file {self.path} in {round(time() - start, 2)}s!')
        if not name:
            name = str(self.path)
        self.circuit = Circuit(name=name)

        return self._populate_circuit(modules_dict['modules'], self.circuit)

    def _populate_circuit(self, modules_dict: Dict[str, YosysModule], circuit: Circuit) -> Circuit:
        self._module_definitions.update(modules_dict.keys())
        for mname in modules_dict:
            s = time()
            LOG.info(f'Building module {mname}...')
            circuit.add_module(self._populate_module(Module(raw_path=mname), modules_dict[mname]))
            # TODO check for multiple top modules!
            if 'attributes' in modules_dict[mname] and 'top' in modules_dict[mname]['attributes']:
                LOG.info(f'Setting module {mname} as new top module as specified in the netlist!')
                circuit.set_top(mname)
            LOG.info(f'Built module {mname} in {round(time() - s, 2)}s!')
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
            for wire_name, wire_data in tqdm(module_dict['netnames'].items(), desc='Wire building progress'):
                w_path = f'{module.name}.{wire_name}'
                msb_first = 'upto' not in wire_data
                w = Wire(raw_path=w_path, msb_first=msb_first, module=module)
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
            for port_name, port_data in tqdm(module_dict['ports'].items(), desc='Port building progress'):
                if CFG.simplify_escaped_identifiers:
                    port_name = self.simplify_port_name(port_name, f'{module.name}')
                p_path = f'{module.name}.{port_name}'
                direction = PortDirection.get(port_data['direction']) if 'direction' in port_data else PortDirection.UNKNOWN
                msb_first = 'upto' not in port_data or port_data['upto'] != 1
                p = Port(raw_path=p_path, direction=direction, msb_first=msb_first, module_or_instance=module)
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
            LibUtils.change_current_module(module)
            LOG.debug(f'Building {len(module_dict["cells"])} instances...')
            start = time()
            for inst_name, inst_data in tqdm(module_dict['cells'].items(), desc='Instance building progress'):
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

        # TODO mapping of different ffs
        inst_path = f'{module.name}.{inst_name}'
        inst = self._get_inst(type_str, inst_path)
        inst.module = module
        self._build_metadata(inst, inst_data)
        self._build_parameters(inst, inst_data)
        self._instance_post_processing(inst, inst_data)
        self._build_instance_ports(module, inst, inst_data)
        module.add_instance(inst)

    def _build_instance_ports(self, module: Module, inst: Instance, instance_data_dict: YosysCell) -> None:
        if 'port_directions' in instance_data_dict:
            for port_name, port_connection in instance_data_dict['connections'].items():
                # Default ports in primitives from gate library have placeholder segments
                # They must be removed before assigning read data
                if CFG.simplify_escaped_identifiers:
                    port_name = self.simplify_port_name(port_name, f'{module.name}.{inst.name}')
                if port_name in inst.ports:
                    inst.ports[port_name].segments.clear()
                port_direction = self._build_instance_ports_direction(instance_data_dict['port_directions'], port_name)
                self._build_instance_ports_connections(module, inst, port_name, port_connection, port_direction)
        else:
            LOG.warn(f'Instance port dictionary is not complete for instance {inst.raw_path}!')

    def _build_instance_ports_direction(self, pdirs: Dict[str, str], pname: str) -> PortDirection:
        return PortDirection.UNKNOWN if pname not in pdirs else PortDirection.get(pdirs[pname])

    def _build_instance_ports_connections(
        self, module: Module, inst: Instance, port_name: str, connections: List[BitAlias], directions: PortDirection
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
                dict_holder.parameters[attr_name] = self._try_get_int(attr_val)  # type:ignore

    def _try_get_int(self, str_val: Union[str, int]) -> Union[int, str]:
        if isinstance(str_val, int):
            return str_val
        if all(c == '0' or c == '1' for c in str_val) and str_val:
            return int(str_val, 2)
        return str_val

    def _get_inst(self, type_str: str, inst_path: str) -> Instance:
        is_primitive = type_str[0] == CFG.id_internal
        if is_primitive and type_str not in self.module_definitions:
            inst_cls: Instance = get(self._map_type2gatelib(type_str))  # type:ignore
            return inst_cls(raw_path=inst_path, is_primitive=True, module=None)  # type:ignore
        else:
            self._module_instantiations.add(type_str)
            return Instance(raw_path=inst_path, instance_type=type_str, is_primitive=False, module=None)

    def _map_type2gatelib(self, type_str: str) -> str:
        if CFG.id_internal in type_str and 'dff' in type_str:
            return f'{CFG.id_internal}dff'
        return type_str

    def _dict_must_be_prepared(self, inst_type: str) -> int:
        return CFG.id_internal in inst_type and ('dff' in inst_type or 'mux' in inst_type)

    def _prepare_dict(self, inst_type: str, inst_data: YosysCell) -> None:
        if 'dff' in inst_type:
            self._prepare_dff_dict(inst_type, inst_data)
        if 'mux' in inst_type:
            self._prepare_mux_dict(inst_type, inst_data)

    def _prepare_dff_dict(self, ff_type: str, ff_dict: YosysCell) -> None:
        if 'a' in ff_type:  # FF with asyncronous reset
            ff_dict['port_directions']['RST'] = ff_dict['port_directions'].pop('ARST')
            ff_dict['connections']['RST'] = ff_dict['connections'].pop('ARST')

    def _prepare_mux_dict(self, mux_type: str, mux_data: YosysCell) -> None:
        mux_data['port_directions']['D_0'] = mux_data['port_directions'].pop('A')
        mux_data['port_directions']['D_1'] = mux_data['port_directions'].pop('B')
        mux_data['connections']['D_0'] = mux_data['connections'].pop('A')
        mux_data['connections']['D_1'] = mux_data['connections'].pop('B')

    def _instance_post_processing(self, inst: Instance, inst_data: YosysCell) -> None:
        if isinstance(inst, DFF):
            if 'ARST_VALUE' in inst_data['parameters']:
                rst_val = self._try_get_int(inst_data['parameters']['ARST_VALUE'])
                inst.rst_val_int = int(rst_val)  # This should always be 1 or 0 -- if not, the exception is helpful :D
            if 'ARST_POLARITY' in inst_data['parameters']:
                rst_pol = self._try_get_int(inst_data['parameters']['ARST_POLARITY'])
                inst.rst_polarity = Signal.get(rst_pol)
            if 'CLK_POLARITY' in inst_data['parameters']:
                clk_pol = self._try_get_int(inst_data['parameters']['CLK_POLARITY'])
                inst.clk_polarity = Signal.get(clk_pol)
            if 'EN_POLARITY' in inst_data['parameters']:
                en_pol = self._try_get_int(inst_data['parameters']['EN_POLARITY'])
                inst.en_polarity = Signal.get(en_pol)
        if isinstance(inst, DLatch):
            if 'EN_POLARITY' in inst_data['parameters']:
                en_pol = self._try_get_int(inst_data['parameters']['EN_POLARITY'])
                inst.en_polarity = Signal.get(en_pol)


TYPE_REPLACEMENT_MAP = {
    '§_BUF_': '§buf',
}
