from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Literal, Optional, Set, Union, overload

from pydantic import BaseModel

from netlist_carpentry.core.exceptions import ObjectNotFoundError, PathResolutionError, SignalAssignmentError
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
from netlist_carpentry.core.netlist_elements.mixins.metadata import METADATA_DICT, NESTED_DICT
from netlist_carpentry.core.netlist_elements.mixins.module_base import T_MODULE_PARTS
from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.core.netlist_elements.netlist_element import NetlistElement
from netlist_carpentry.core.netlist_elements.port import Port
from netlist_carpentry.core.netlist_elements.port_segment import PortSegment
from netlist_carpentry.core.netlist_elements.segment_base import _Segment
from netlist_carpentry.core.netlist_elements.wire import Wire
from netlist_carpentry.core.netlist_elements.wire_segment import WireSegment
from netlist_carpentry.core.protocols.signals import LogicLevel
from netlist_carpentry.core.signal import Signal
from netlist_carpentry.scripts.eqy_check import EqyWrapper
from netlist_carpentry.utils.custom_dict import CustomDict
from netlist_carpentry.utils.log import LOG


class Circuit(BaseModel):
    """
    Represents a circuit, which is a collection of modules.

    A circuit consists of one or more modules. All modules are uniquely identified by their names,
    which are stired as keys in a dictionary, where their values are the corresponding Module objects.
    Each module can be part of other modules in the form of instatiations as submodules within a module.
    Furthermore, each circuit can have an associated top-level module, indicating the hierarchical entry point of the circuit.
    """

    name: str
    """The name of the circuit."""
    _modules = CustomDict[str, Module]()
    """A dictionary mapping module names to Module objects."""
    _top_name: str = ''
    """The name of the top-level module in the circuit."""
    _creator: str = ''
    """The name of the circuit's creator."""

    @property
    def modules(self) -> CustomDict[str, Module]:
        """
        Returns the dictionary of modules in the circuit.

        Returns:
            Dict[str, Module]: The dictionary of modules, where the key is the module name and the value is a Module object.
        """
        return self._modules

    @property
    def module_count(self) -> int:
        """The number of modules in the circuit."""
        return len(self)

    @property
    def module_names(self) -> Set[str]:
        """A set of the names of the modules in the circuit."""
        return set(self.modules.keys())

    @property
    def top_name(self) -> str:
        """The name of the top-level module in the circuit."""
        return self._top_name

    @property
    def top(self) -> Module:
        """The top-level module in the circuit."""
        if self.has_top:
            return self[self.top_name]
        raise ObjectNotFoundError(f"No top module found! Name of top module is currently set to '{self.top_name}'!")

    @property
    def has_top(self) -> bool:
        """True, if this circuit has a top-level module. False otherwise."""
        return self.top_name in self.modules

    @property
    def creator(self) -> str:
        """The name of the circuit's creator."""
        return self._creator

    @creator.setter
    def creator(self, new_creator: str) -> None:
        """Sets the name of the circuit's creator."""
        self._creator = new_creator

    def __getitem__(self, key: str) -> Module:
        """Returns a module from the circuit that has the given name."""
        return self.modules[key]

    def __len__(self) -> int:
        """The size of the circuit, which is the number of modules in the circuit."""
        return len(self.modules)

    def __iter__(self) -> Iterator[Module]:  # type: ignore[override]
        """Iterator over the modules in the circuit."""
        return iter(self.modules.values())

    @property
    def first(self) -> Module:
        """
        Returns the first module in the circuit.

        Useful for circuits that only contain a single module.

        Raises:
            IndexError: If the circuit does not have any modules, so no first module exists.
        """
        first = self.get_module_at_idx(0)
        if first is not None:
            return first
        raise IndexError(f'No defined first module: Circuit {self.name} does not have any modules!')

    def add_module(self, module: Module) -> Module:
        """
        Adds a module to the circuit.

        Args:
            module (Module): The module to add.

        Returns:
            Module: The module that was added.
        """
        return self.modules.add(module.name, module)

    def add_from_circuit(self, other_circuit: Circuit) -> Dict[str, Module]:
        """
        Adds all modules from a given circuit to this circuit.

        The modules are not copied in the sense that new objects are created.
        The objects are added by reference, meaning that if a module in one circuit is changed,
        it will also change in the other circuit.

        Args:
            other_circuit (Circuit): The circuit of which the modules should be added.

        Returns:
            Dict[str, Module]: A dict of all module names and modules from the given circuit that were added to this circuit.
        """
        for m in other_circuit:
            self.add_module(m)
        return other_circuit.modules

    def create_module(self, name: str) -> Module:
        """
        Creates a new module with the given name and adds it to the circuit.

        Args:
            name (str): The name of the module to create.

        Returns:
            Module: The module that was created and added to this circuit.
        """
        return self.add_module(Module(raw_path=name))

    def remove_module(self, module_name: str) -> None:
        """
        Removes a module from the circuit.

        Args:
            module_name (str): The name of the module to remove.

        Raises:
            Exception: If the module name is the same as the top module name and no new top module is set.
        """
        if module_name == self.top_name:
            LOG.warn(f"Removing top module '{module_name}'! Set a new top module using Circuit.set_top(), otherwise hierarchy cannot be determined!")
            self._top_name = ''
        self.modules.remove(module_name)

    def get_module(self, module_name: str) -> Optional[Module]:
        """
        Gets a module from the circuit.

        Args:
            module_name (str): The name of the module to get.

        Returns:
            Optional[Module]: The module with the given name, if it exists.
        """
        return self.modules.get(module_name, None)

    def get_module_at_idx(self, index: int) -> Optional[Module]:
        """
        Returns the module with the given index.

        Internally, the modules are stored in a dictionary, so there is no forced order.
        Therefore, this function enumerates the modules based on the order in the dictionary and returns
        the module at the given index.
        If there is no module at the given index (i.e. the index is out of bounds), returns None.

        Args:
           index (int): The index of the module to return.

        Returns:
            Optional[Module]: The module at the given index, or None if the circuit has less modules than the given index.
        """
        return next((m for i, m in enumerate(self) if i == index), None)

    def set_top(self, module: Union[str, Module]) -> None:
        """
        Sets the name of the top-level module in the circuit.

        Args:
            module (Union[str, Module]): The name of the new top-level module in the circuit, or the Module object itself.

        Raises:
            ObjectNotFoundError: If no module exists with the given name.
        """
        if isinstance(module, Module):
            module = module.name
        if module in self.modules:
            self._top_name = module
        else:
            raise ObjectNotFoundError(f'Cannot set top module: No module with name "{module}" exists in the circuit!')

    @overload
    def get_from_path(self, path: str) -> NetlistElement: ...
    @overload
    def get_from_path(self, path: InstancePath) -> Instance: ...
    @overload
    def get_from_path(self, path: PortPath) -> Port[Union[Module, Instance]]: ...
    @overload
    def get_from_path(self, path: PortSegmentPath) -> PortSegment: ...
    @overload
    def get_from_path(self, path: WirePath) -> Wire: ...
    @overload
    def get_from_path(self, path: WireSegmentPath) -> WireSegment: ...
    @overload
    def get_from_path(self, path: ElementPath) -> NetlistElement: ...

    def get_from_path(self, path: Union[str, T_PATH_TYPES]) -> Union[NetlistElement, T_MODULE_PARTS]:
        """
        Retrieves an element from the circuit based on a given ElementPath.

        The element can be of any type, including ports, wires or instances.
        This method tries to recursively break down the path to find the desired object.
        Given a path `module.inst1.inst2`, this method will return the instance `inst2`
        of the instance `inst1` inside the module `module`.
        Here, it is important that the type of the ElementPath is specified correctly.
        For the given example path, the type must be EType.INSTANCE, otherwise this method will
        be unable to find the instance.

        Args:
           path (ElementPath): A certain ElementPath that points to an element within the circuit.

        Returns:
           NetlistElement: The object corresponding to the path.

        Raises:
            PathResolutionError: If the given path could not be resolved to an object,
                either because the path is malformed, or no associated object exists.
        """
        if isinstance(path, str):
            path = self.get_path_from_str(path)
        if isinstance(path, ElementPath):
            return self._get_from_path(path)
        raise PathResolutionError(f'Did not find object associated with path {path}!')

    def _get_from_path(self, path: ElementPath) -> NetlistElement:
        # Heuristic: 1st element is a module name
        # Last element is of the type path.type
        # Recursively enter deeper layers in the hierarchy as long as there are still instances to enter
        # Otherwise try to find path target in the module at the current hierarchy layer
        if not path:
            raise PathResolutionError(f'The provided path is empty: {path}')
        mapping = path.type_mapping
        path_mapping = {
            EType.UNSPECIFIED: ElementPath,
            EType.MODULE: ModulePath,
            EType.INSTANCE: InstancePath,
            EType.PORT: PortPath,
            EType.PORT_SEGMENT: PortSegmentPath,
            EType.WIRE: WirePath,
            EType.WIRE_SEGMENT: WireSegmentPath,
        }
        module_name = mapping[0][0]
        module = self[module_name]
        instance_nr = sum(etype == EType.INSTANCE for _, etype in mapping)
        if instance_nr > 1:
            nxt_inst = mapping[1][0]
            if nxt_inst in module.instances:
                inst = module.instances[mapping[1][0]]
                raw_curr_path = '.'.join(name for name, _ in mapping[2:])
                new_path_str = f'{inst.instance_type}.{raw_curr_path}'
                path_type = path_mapping[mapping[-1][1]]
                return self.get_from_path(path_type(raw=new_path_str))
        return self[module_name].get_from_path(path)

    def get_path_from_str(self, path_str: str, sep: str = '.') -> ElementPath:
        """
        Returns an appropriate ElementPath object for a given path.

        Based on certain heuristics and the modules present in this circuit, the type of the path is assumed.
        The first element in the path is assumed to be a module, and any following element can only be an instance,
        port or wire. The actual type is retrieved by checking the instances, ports and wires of the module found
        in the first step for any matching instances. If it is a wire, it may only be followed by an integer
        indicating the corresponding segment. Analogously, if it is a port, and it is followed by an integer, the
        path points to a port segment. In case it is an instance, the path is further investigated, as an instance
        can be followed by a port in the path or another instance (if it is a submodule instance, and the path
        points to an instance within the submodule), which is then resolved recursively until the whole path
        is decoded. If no path can be retrieved, `None` is returned instead.

        Args:
            path_str (str): The hierarchical path to an object of this circuit as a plain string.
            sep (str, optional): The character separating the individual hierarchical levels. Defaults to '.'.
                If the path uses a different separating character, it is replaced in the path by the '.'.
                Make sure, the '.' is not part of an element of the hierarchical path.

        Returns:
            Optional[ElementPath]: An appropriate element path object from the given path based on certain heuristics.
                Is None, if no path object can be built.
        """
        elements = path_str.split(sep)
        path_str = '.'.join(elements)  # Replace original separator with dot for conformity
        if elements[0] not in self.module_names:
            raise PathResolutionError(f'Cannot resolve path {path_str}: No module found with name {elements[0]} in circuit {self.name}!')
        while len(elements) > 1:
            module_name = elements.pop(0)
            module = self[module_name]
            if elements[0] in module.instances:
                module_inst = module.instances[elements[0]]
                next_module_name = module_inst.instance_type
                if len(elements) > 1:
                    if next_module_name not in self.module_names:
                        break
                    elements[0] = next_module_name
            else:
                break
        return self._get_path_from_str(path_str, module, elements)

    def _get_path_from_str(self, path_str: str, module: Module, processed_elements: List[str]) -> ElementPath:
        object_name = processed_elements[0]
        if object_name in module.instances:
            return self._get_path_from_str_inst(path_str, module.instances[object_name], processed_elements)
        elif object_name in module.ports:
            return self._get_path_from_str_port(path_str, module.ports[object_name], processed_elements)
        elif object_name in module.wires:
            return self._get_path_from_str_wire(path_str, module.wires[object_name], processed_elements)
        raise PathResolutionError(f'Cannot resolve path {path_str}: No object found with name {object_name} in module {module.name}!')

    def _get_path_from_str_inst(self, path_str: str, inst: Instance, processed_elements: List[str]) -> ElementPath:
        if len(processed_elements) == 1:
            return InstancePath(raw=path_str)
        if len(processed_elements) == 2 and processed_elements[1] in inst.ports:
            return PortPath(raw=path_str)
        if len(processed_elements) == 3 and processed_elements[1] in inst.ports and processed_elements[2].isnumeric():
            return PortSegmentPath(raw=path_str)
        raise PathResolutionError(f'Cannot resolve path {path_str}: The last resolved object is an instance with path {path_str}!')

    def _get_path_from_str_port(self, path_str: str, port: Port, processed_elements: List[str]) -> ElementPath:
        if len(processed_elements) == 1:
            return PortPath(raw=path_str)
        elif len(processed_elements) == 2 and processed_elements[1].isnumeric() and int(processed_elements[1]) in port.segments:
            return PortSegmentPath(raw=path_str)
        raise PathResolutionError(f'Cannot resolve path {path_str}: The last resolved object is a port with path {path_str}!')

    def _get_path_from_str_wire(self, path_str: str, wire: Wire, processed_elements: List[str]) -> ElementPath:
        if len(processed_elements) == 1:
            return WirePath(raw=path_str)
        elif len(processed_elements) == 2 and processed_elements[1].isnumeric() and int(processed_elements[1]) in wire.segments.keys():
            return WireSegmentPath(raw=path_str)
        raise PathResolutionError(f'Cannot resolve path {path_str}: The last resolved object is a wire with path {path_str}!')

    @overload
    def set_signal(self, path: str, signal_value: LogicLevel) -> None: ...
    @overload
    def set_signal(self, path: str, signal_value: Signal) -> None: ...

    def set_signal(self, path: str, signal_value: Union[LogicLevel, Signal]) -> None:
        element = self.get_from_path(path)
        if element is None:
            raise ObjectNotFoundError(f'Cannot set signal: no corresponding object for path {path}!')
        if not element.can_carry_signal:
            raise SignalAssignmentError(f'Cannot set signal on element {element.name} of type {element.type}')
        if isinstance(signal_value, str):
            signal_value = Signal.get(signal_value)
        if isinstance(element, _Segment):
            element.set_signal(signal_value)
        elif isinstance(element, Wire) or isinstance(element, Port):
            for idx in element.segments:
                element.set_signal(signal_value, idx)

    def write(self, output_file_path: Union[str, Path], overwrite: bool = False) -> None:
        """
        Writes a Verilog file for this circuit to the given location.

        If the output file already exists and overwrite is False, it will raise an error.

        Args:
            output_file_path (Union[str, Path]): The path to write the Verilog representation of the circuit to.
            overwrite (bool): Whether to overwrite a file if it already exists. Defaults to False.

        Returns:
            None
        """
        from netlist_carpentry import write

        output_path = Path(output_file_path)
        write(self, output_path, overwrite)

    @overload
    def prove_equivalence(self, gold_design: List[str], out_dir: str, eqy_script_path: str = '', gold_top_module: str = '') -> int: ...
    @overload
    def prove_equivalence(self, gold_design: 'Circuit', out_dir: str, eqy_script_path: str = '', gold_top_module: str = '') -> int: ...

    def prove_equivalence(self, gold_design: Union[List[str], 'Circuit'], out_dir: str, eqy_script_path: str = '', gold_top_module: str = '') -> int:
        """
        Proves equivalence of the circuit against a set of gold Verilog files.

        In the context of comparing two digital designs, `gold` is used to describe a reference design or implementation
        that is considered to be correct or the "golden reference".
        The complementary design (i.e. the optimized, modified or synthesized design) is refered to as `gate` design,
        as it is often a gate-level implementation of the previously designed circuit.
        This function compares the gate design with the gold Verilog files to ensure that they are equivalent using Yosys EQY.

        Args:
            gold_design (Union[List[str], Circuit]): A list of paths to the gold Verilog files.
                Alternatively, another Circuit object can be provided, which is then used for comparison.
                In this case, the Circuit object is first converted back to Verilog and then the equivalence check is executed.
            out_dir (str): The directory to write the output files to.
            eqy_script_path (str, optional): The path to the eqy script. If not provided, an eqy script will be generated. Defaults to ''.
            gold_top_module (str, optional): The name of the top module in the gold Verilog files. Defaults to '',
                in which case the top module will be inferred from this circuit object.

        Returns:
            int: The return code of the eqy tool.
        """
        if isinstance(gold_design, Circuit):
            out_file = f'{out_dir}/{gold_design.name}_out.v'
            gold_design.write(out_file, overwrite=True)
            gold_design = [out_file]
        eqy_out = out_dir + '/out'
        Path(eqy_out).mkdir(parents=True, exist_ok=True)
        generate_script = not eqy_script_path  # If no path is provided, generate the eqy script
        if not eqy_script_path:
            eqy_script_path = out_dir + '/script.eqy'
        eqy = EqyWrapper(eqy_script_path)
        output_vfile = f'{out_dir}/{self.name}_out.v'
        self.write(output_vfile, overwrite=True)
        if not gold_top_module:
            gold_top_module = self.top_name
        if generate_script:
            eqy.create_eqy_file(gold_design, gold_top_module, [output_vfile], self.top_name)
        eqy.proc(gold_design[0], gold_top_module, output_vfile, self.top_name)
        return eqy.run_eqy(eqy_out, overwrite=True)

    def optimize(self) -> bool:
        """
        Optimizes the circuit by applying optimizations to each module.

        Returns:
            bool: True if at least one optimization was applied to at least one module. False otherwise.
        """
        any_optimized = False
        for mname, m in self.modules.items():
            LOG.info(f'Optimizing module {mname}...')
            any_optimized |= m.optimize()
        return any_optimized

    def evaluate(self) -> None:
        """
        Evaluates the circuit.

        This method evaluates the top module in the circuit and all modules that are part of it, in a top-down manner.
        """
        self.top.evaluate(self.modules)

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
        md_dict: METADATA_DICT = {}
        for module in self:
            md_module = module.normalize_metadata(include_empty=include_empty, sort_by=sort_by, filter=filter)
            for cat, val in md_module.items():
                if cat in md_dict:
                    md_dict[cat].update(val)
                else:
                    md_dict[cat] = val
        with open(path, 'w', encoding='utf-8') as f:
            # ensure_ascii=False: special characters are displayed correctly
            f.write(json.dumps(md_dict, indent=2, ensure_ascii=False))
