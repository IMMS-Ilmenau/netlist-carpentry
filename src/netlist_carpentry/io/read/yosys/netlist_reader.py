"""Module handling the reading of a Yosys-generated JSON netlist and transformation into corresponding Python objects."""
# mypy: disable-error-code="unreachable"

import json
import re
from pathlib import Path
from time import time
from typing import Dict, Optional, Set, Union

from tqdm import tqdm

from netlist_carpentry import CFG, LOG, Circuit, Module
from netlist_carpentry.io.read.abstract_reader import AbstractReader
from netlist_carpentry.io.read.yosys.netlist_types import (
    ModuleNameMapping,
    NetNumberMappingDict,
    YosysData,
    YosysModule,
)


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
            netlist_data = YosysData(**json.loads(f.read()))  # type: ignore[misc]
            return self._preprocess_dict(netlist_data)

    def _preprocess_dict(self, nl_data: YosysData) -> YosysData:
        LOG.debug(f"Replacing all special characters with their internal representation, which is currently set to '{CFG.id_internal}'...")
        nl_data.clean()

        for mname in list(nl_data.modules or {}):
            simple_name = self.simplify_module_name(mname)
            if simple_name != mname:
                LOG.debug(f"Simplifying module name '{mname}' to '{simple_name}'...")
                nl_data.replace(mname, simple_name)
        return nl_data

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
        modules_data = self.read()
        LOG.debug(f'Read Yosys netlist from file {self.path} in {round(time() - start, 2)}s!')
        if name is None:
            name = str(self.path.stem)
        self.circuit = Circuit(name=name)

        return self._populate_circuit(modules_data.modules or {}, self.circuit)

    def _populate_circuit(self, modules_dict: Dict[str, YosysModule], circuit: Circuit) -> Circuit:
        self._module_definitions.update(modules_dict.keys())
        for mname, yosys_module in modules_dict.items():
            s = time()
            LOG.debug(f'Building module {mname}...')
            circuit.add_module(self._populate_module(Module(name=mname), yosys_module))
            # TODO check for multiple top modules!
            if yosys_module.attributes and 'top' in yosys_module.attributes:
                LOG.debug(f'Setting module {mname} as new top module as specified in the netlist!')
                circuit.set_top(mname)
            LOG.debug(f'Built module {mname} in {round(time() - s, 2)}s!')
        return circuit

    def _populate_module(self, module: Module, module_dict: YosysModule) -> Module:
        self._build_wires(module, module_dict)
        self._build_ports(module, module_dict)
        self._build_instances(module, module_dict)
        module_dict.build_parameters(module)
        module_dict.build_metadata(module)

        return module

    def _build_wires(self, module: Module, module_dict: YosysModule) -> None:
        self.net_number_mapping[module.name] = {}
        if module_dict.netnames:
            LOG.debug(f'Building {len(module_dict.netnames)} wires...')
            start = time()
            for wire_name, wire_data in tqdm(module_dict.netnames.items(), desc='Wire building progress', leave=False):
                wire_data.build_wire(self.net_number_mapping[module.name], module, wire_name)
            LOG.debug(f'Built {len(module_dict.netnames)} wires in {time() - start:.2f}s.')

    def _build_ports(self, module: Module, module_dict: YosysModule) -> None:
        if module_dict.ports:
            LOG.debug(f'Building {len(module_dict.ports)} module ports...')
            start = time()
            for port_name, port_data in tqdm(module_dict.ports.items(), desc='Port building progress', leave=False):
                port_data.build_port(self.net_number_mapping[module.name], module, port_name)
            LOG.debug(f'Built {len(module_dict.ports)} module ports in {time() - start:.2f}s.')

    def _build_instances(self, module: Module, module_dict: YosysModule) -> None:
        if module_dict.cells:
            LOG.debug(f'Building {len(module_dict.cells)} instances...')
            start = time()
            for inst_name, inst_data in tqdm(module_dict.cells.items(), desc='Instance building progress', leave=False):
                inst = inst_data.build_instance(self.module_definitions, self.net_number_mapping[module.name], module, inst_name)
                if not inst.is_primitive:
                    self._module_instantiations.add(inst.instance_type)

            LOG.debug(f'Built {len(module_dict.cells)} instances in {time() - start:.2f}s.')
