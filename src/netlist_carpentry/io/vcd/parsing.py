from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Dict, List, Optional, Set, Tuple, Union

from pydantic import NonNegativeInt, PositiveInt

from netlist_carpentry import CFG, LOG, Circuit, Module
from netlist_carpentry.core.exceptions import VcdLoadingError
from netlist_carpentry.io.vcd.wrapper import VCDScope, VCDVar, VCDWaveform

STR_DICT = Dict[str, Union[str, 'STR_DICT']]
VCD_MAPPING = Dict[str, Module]
SIGNAL_TOGGLE_DICT = Dict[Tuple[int, ...], List[VCDVar]]
SIGNAL_NAME = str
SIGNAL_GROUP = List[str]
SIGNAL_GROUPS = List[SIGNAL_GROUP]
SIGNAL_VALUE = Union[int, str]
SIGNAL_TOGGLE_TIME = int
SIGNAL_CHANGE = Tuple[SIGNAL_TOGGLE_TIME, SIGNAL_VALUE]
SIGNAL_CHANGES = Tuple[SIGNAL_CHANGE, ...]
SIGNAL_CHANGE_DICT = Dict[SIGNAL_NAME, SIGNAL_CHANGES]


def _get_hierarchy_dict(wf: VCDWaveform, curr_scope: VCDScope, curr_dict: STR_DICT) -> None:
    curr_dict[curr_scope.name] = {}
    for subscope in curr_scope.scopes:
        _get_hierarchy_dict(wf, subscope, curr_dict[curr_scope.name])  # type: ignore[arg-type]


def get_hierarchy_dict(wf: VCDWaveform) -> STR_DICT:
    """Returns a nested dictionary containing all scopes and associated subscopes.

    For example, if a scope `Scope1` contains a scope `Scope2`, which in turn contains a scope `Scope3`,
    the result will be:
    ```python
    { "Scope1": { "Scope2": { "Scope3": {} } } }
    ```

    Args:
        wf (VCDWaveform): The waveform of which the hierarchy should be extracted.

    Returns:
        STR_DICT: A dictionary of all scopes, where for each scope key, a nested dictionary contains all subscopes.
    """
    scope_dict: STR_DICT = {}
    for scope in wf.top_scopes:
        _get_hierarchy_dict(wf, scope, scope_dict)
    return scope_dict


def get_scope(wf: VCDWaveform, scope_name: str) -> VCDScope:
    """Returns the scope with the given name, if found.

    Args:
        wf (VCDWaveform): A waveform object.
        scope_name (str): The name of the scope, where the corresponding object is wanted.

    Raises:
        VcdLoadingError: If no scope with the given name was found.

    Returns:
        VCDScope: The scope with the given name.
    """
    scope = _get_scope(wf.top_scopes, scope_name)
    if scope is not None:
        return scope
    raise VcdLoadingError(f"No scope '{scope_name}' was found!")


def _get_scope(scope_list: List[VCDScope], scope_name: str) -> Optional[VCDScope]:
    for s in scope_list:
        for sub in s.scopes:
            if sub.name == scope_name:
                LOG.debug(f'Found scope: {s.name}')
                return sub
        return _get_scope(s.scopes, scope_name)
    return None


def map_names_to_circuit(c: Circuit, wf: VCDWaveform, top_vcd_scope: str) -> VCD_MAPPING:
    """Maps all scope names to the corresponding circuit objects, so that for each scope, an associated module exists.

    Args:
        c (Circuit): The circuit to map
        wf (VCDWaveform): The waveform object with the scopes and signal data.
        top_vcd_scope (str): The name of the top-level VCD scope.

    Returns:
        VCD_MAPPING: A mapping of scope names (full paths) to corresponding modules of the given circuit.
    """
    mapping: VCD_MAPPING = {}
    scope = get_scope(wf, top_vcd_scope)
    mapping[scope.full_name] = c.top
    _map_names_to_circuit(c, c.top, scope, mapping)
    return mapping


def _map_names_to_circuit(c: Circuit, module: Module, scope: VCDScope, curr_mapping: VCD_MAPPING) -> None:
    for s in scope.scopes:
        if s.name not in module.instances:
            raise VcdLoadingError(f'Cannot map VCD scope object {s.name} to an instance of module {module.name}!')
        if not module.instances[s.name].is_module_instance:
            raise VcdLoadingError(f'No module instance found for instance {s.full_name}!')
        curr_mapping[s.full_name] = module.instances[s.name].module_definition  # type: ignore[assignment]
        _map_names_to_circuit(c, curr_mapping[s.full_name], s, curr_mapping)


def apply_vcd_data(c: Circuit, wf: VCDWaveform, top_scope: str, scope: VCDScope = None) -> None:
    """Applies the VCD data from the given waveform to all wires of the circuit.

    For each signal from the VCD waveform, a corresponding wire in the circuit is retrieved.
    This wire's metadata receives a new category `vcd`, into which the value trace for the signal is stored.
    With `Wire.metadata.vcd`, all stored VCD data can be seen afterwards.
    The `vcd` category is a dictionary, where the key is the full hierarchical path of the VCD variable.
    The value is a list of signal value changes as tuples, where the first element is the timestamp,
    and the second element is the new signal value.

    If a module is instantiated multiple times throughout the circuit, the hierarchical path of each VCD variable
    will keep the VCD data uniquely identifiable.
    This means, if a module is instantiated twice, the wire's VCD metadata dictionary will contain two entries
    (if the VCD waveform captured both traces) together with value change list, one for each module instance.

    Args:
        c (Circuit): The circuit, in which the VCD signals should be mapped to the corresponding wires.
        wf (VCDWaveform): A VCD waveform that was generated by simulating the given circuit with a certain testbench.
        top_scope (str): The name of the top scope. Is required to identify which scope of the VCD waveform
            matches the top-level module of the circuit.
        scope (VCDScope, optional): Optionally, a scope can be provided.
            If provided, only VCD vars inside this scope (and subscopes) are applied to the given circuit.
            Defaults to None.
    """
    if scope is None:
        for s in wf.top_scopes:
            apply_vcd_data(c, wf, top_scope, s)
    else:
        _apply_vcd_scope(c, wf, top_scope, scope)
        for inner_scope in scope.scopes:
            apply_vcd_data(c, wf, top_scope, inner_scope)


def _apply_vcd_scope(c: Circuit, wf: VCDWaveform, top_scope: str, scope: VCDScope):
    scope_map = map_names_to_circuit(c, wf, top_scope)
    if scope.full_name in scope_map:
        m = scope_map[scope.full_name]
        _apply_vcd_module(m, wf, scope)
    else:
        LOG.warn(f'No instance with name {scope.name} found in circuit {c.name}!')


def _apply_vcd_module(m: Module, wf: VCDWaveform, scope: VCDScope):
    for var in scope.vars:
        internal_var_name = var.name.replace(CFG.id_external, CFG.id_internal)
        if internal_var_name in m.wires:
            LOG.debug(f'Found a corresponding wire for VCD var {var.name}!')
            m.wires[internal_var_name].metadata.add_category('vcd')
            m.wires[internal_var_name].metadata.vcd.update({var.full_name: var.all_changes})
        else:
            LOG.debug(f'No wire for VCD var {var.name}, could be a parameter or something else...')


def equal_toggles(wf: VCDWaveform, scope: Optional[VCDScope] = None, vcd_vars: Optional[List[Union[str, VCDVar]]] = None) -> SIGNAL_TOGGLE_DICT:
    """Returns a dictionary of timestamps and a list of associated VCD vars that toggle on the given timestamps.

    Args:
        wf (VCDWaveform): The waveform in which equally toggling signals should be identified.
        scope (Optional[VCDScope], optional): A scope in which the signals should be analyzed. Defaults to None,
            in which case, all scopes (i.e. all vars throughout the whole hierarchy) are analyzed.
        vcd_vars (Optional[List[Union[str, VCDVar]]]): A list of vars (or names of vars) which should be analyzed.
            Must be a subset of all existing vars within the given scope or the waveform.
            Defaults to None, in which case the whole scope or the waveform is considered.
            However, if a list is given and empty, no vars are checked, and the result will be an empty dictionary.

    Returns:
        SIGNAL_TOGGLE_DICT: A dictionary, where each key is a tuple of timestamps,
            and the associated list consists of VCD vars that toggle at the given timestamps.
    """
    if vcd_vars is None:
        vcd_vars = list(wf.all_vars.values()) if scope is None else scope.vars
    else:
        vcd_vars: List[VCDVar] = [v if isinstance(v, VCDVar) else wf.all_vars[v] for v in vcd_vars]
    var_dict: SIGNAL_TOGGLE_DICT = defaultdict(list)
    for var in vcd_vars:
        var_dict[tuple(var.change_times)].append(var)
    return var_dict


def filter_signals(
    wf: VCDWaveform,
    scope: Optional[VCDScope] = None,
    vcd_vars: Optional[List[Union[str, VCDVar]]] = None,
    min_occurences: PositiveInt = 1,
    min_changes: NonNegativeInt = 0,
) -> SIGNAL_TOGGLE_DICT:
    """Filters signals from the given VCD waveform based on how often they toggle or how many other signals toggle together with them.

    Args:
        wf (VCDWaveform): The waveform in which equally toggling signals should be identified.
        scope (Optional[VCDScope], optional): The scope in which signals should be filtered. Defaults to None.
            If set to None, all vars from the waveform are considered and filtered.
        vcd_vars (Optional[List[Union[str, VCDVar]]]): A list of vars (or names of vars) which should be analyzed.
            Must be a subset of all existing vars within the given scope or the waveform.
            Defaults to None, in which case the whole scope or the waveform is considered.
            However, if a list is given and empty, no vars are checked, and the result will be an empty dictionary.
        min_occurences (PositiveInt, optional): The minimal number of equal signals to include. If e.g. set to `2`,
            the resulting dictionary will only contain signal traces, where at least 2 signals always have the same toggling timestamps.
            Defaults to 1, which means that signals will also be included if they are "unique" regarding their toggling timestamps.
        min_changes (NonNegativeInt, optional): The minimal number of signal changes. If e.g. set to `1`,
            only signals are included that change their value at least once. Defaults to 0.

    Returns:
        SIGNAL_TOGGLE_DICT: A dictionary of toggling signals, where each key is a tuple of timestamps,
            and the associated list consists of VCD vars that toggle at the given timestamps, matching the given criterias.
    """
    var_dict = equal_toggles(wf, scope, vcd_vars)
    # Filter out all those signals without at least 'min_occurences' corresponding other signal with same changes
    # Also filter out all signals that have less than 'min_changes' toggles (i.e. nr of timestamps minus 1)
    vars_to_remove: Set[Tuple[int, ...]] = set()
    for vtuple in var_dict:
        obj = var_dict[vtuple]
        if len(obj) < min_occurences or len(vtuple) - 1 < min_changes:
            vars_to_remove.add(vtuple)
    for vtuple in vars_to_remove:
        var_dict.pop(vtuple)
    return var_dict


def filter_signals_per_scope(
    wf: VCDWaveform,
    scope: Optional[VCDScope],
    signal_dict: Dict[str, SIGNAL_TOGGLE_DICT],
    vcd_vars: Optional[List[Union[str, VCDVar]]] = None,
    min_occurences: PositiveInt = 1,
    min_changes: NonNegativeInt = 0,
) -> None:
    """Filters signals from the given VCD waveform based on how often they toggle or how many other signals toggle together with them and orders them by scope.

    This is done by recursively iterating through all subscopes, so that the given `signal_dict` in populated for every scope.
    The result then contains alls variables, starting from the given scope and below, so that each subdict only contains matching signals for that specific scope.
    This is useful to collect signals toggling at the same timestamps within a given module,
    especially in regards to optimization and simplification of said module.

    Args:
        wf (VCDWaveform): The waveform in which equally toggling signals should be identified.
        scope (Optional[VCDScope], optional): The scope in which signals should be filtered. Defaults to None.
            If set to None, all vars from the waveform are considered and filtered.
        signal_dict (Dict[str, SIGNAL_TOGGLE_DICT]): A dictionary which is updated and expanded in every iteration.
        vcd_vars (Optional[List[Union[str, VCDVar]]]): A list of vars (or names of vars) which should be analyzed.
            Must be a subset of all existing vars within the given scope or the waveform.
            Defaults to None, in which case the whole scope or the waveform is considered.
            However, if a list is given and empty, no vars are checked, and the result will be an empty dictionary.
        min_occurences (PositiveInt, optional): The minimal number of equal signals to include. If e.g. set to `2`,
            the resulting dictionary will only contain signal traces, where at least 2 signals always have the same toggling timestamps.
            Defaults to 1, which means that signals will also be included if they are "unique" regarding their toggling timestamps.
        min_changes (NonNegativeInt, optional): The minimal number of signal changes. If e.g. set to `1`,
            only signals are included that change their value at least once. Defaults to 0.

    Returns:
        SIGNAL_TOGGLE_DICT: A dictionary of toggling signals, where each key is a scope name and the value is a dictionary.
            Within this inner dictionary, the keys are tuples of timestamps (comparable to the results of the `equal_toggles` and
            `filter_signals` functions), and the associated list consists of VCD vars that toggle at the given timestamps, matching the given criterias.
    """
    if scope is None:
        for s in wf.top_scopes:
            filter_signals_per_scope(wf, s, signal_dict, vcd_vars, min_occurences, min_changes)
    else:
        signal_dict[scope.full_name] = filter_signals(wf, scope, vcd_vars, min_occurences=min_occurences, min_changes=min_changes)
        for s in scope.scopes:
            filter_signals_per_scope(wf, s, signal_dict, vcd_vars, min_occurences, min_changes)


def _refine_partition(current_partition: Optional[SIGNAL_GROUPS], current_file_signatures: SIGNAL_CHANGE_DICT) -> Optional[SIGNAL_GROUPS]:
    if current_partition is None:
        # First file: Group signals purely by their value history in this file
        initial_groups: DefaultDict[SIGNAL_CHANGES, SIGNAL_GROUP] = defaultdict(list)
        for name, signature in current_file_signatures.items():
            initial_groups[signature].append(name)
        current_partition: SIGNAL_GROUPS = list(initial_groups.values())
        LOG.debug(f'Initial partition has {len(current_partition)} groups with a total of {sum(len(g) for g in current_partition)} signals!')
    else:
        # Subsequent files: Split existing groups based on the new file's data
        next_partition: SIGNAL_GROUPS = []

        for group in current_partition:
            subgroups: DefaultDict[SIGNAL_CHANGES, SIGNAL_GROUP] = defaultdict(list)
            for signal_name in group:
                sig = current_file_signatures.get(signal_name)
                subgroups[sig].append(signal_name)
            next_partition.extend(subgroups.values())

        LOG.debug(f'Refined partition has {len(current_partition)} groups with a total of {sum(len(g) for g in current_partition)} signals!')
        current_partition = next_partition
    if len(current_partition) == 0:
        return None  # Either no files or no functioning partitions (e.g. no signals toggle together)
    return current_partition


def partition_all_vcd_signals(vcd_filepaths: List[Union[Path, str]]) -> Optional[SIGNAL_GROUPS]:
    """Partition all VCD signals from the given files, such that all signals with equal toggling behavior and values are grouped together.

    **The names of the top-level scopes (i.e. the testbench names) must match in all VCD files, otherwise grouping and matching will not work, as the root names would differ!**

    Args:
        vcd_filepaths (List[Path, str]): The paths to the VCD files to analyze and partition.

    Returns:
        Optional[List[List[str]]]: A partitioning list of all VCD vars,
            where each list consists of VCD var names that always have equal values and might thus be logically equivalent.
    """
    current_partition = None
    found_top_name = None
    i = 1
    for filepath in vcd_filepaths:
        LOG.info(f'Processing Waveform file {filepath} ({i}/{len(vcd_filepaths)}) ...')
        wf = VCDWaveform(filepath)
        raw_data = filter_signals(wf, min_changes=1)
        i += 1
        LOG.debug(f'Found {len(raw_data)} groups of signals always toggling together in file {filepath}.')

        # Lookup Map for this specific file: Name -> Value History
        current_file_signatures: SIGNAL_CHANGE_DICT = {}

        for var_list in raw_data.values():
            for vcd_var in var_list:
                signature = tuple(vcd_var.all_changes)
                current_file_signatures[vcd_var.full_name] = signature
                top_name = vcd_var.full_name.split('.')[0]
                if found_top_name is None:
                    found_top_name = top_name
                elif found_top_name != top_name:
                    raise VcdLoadingError(
                        f"Found different testbench names '{top_name}' and '{found_top_name}', cannot map signals if testbench names do not match!"
                    )

        current_partition = _refine_partition(current_partition, current_file_signatures)
        if current_partition is None:
            break  # No matching signals left, since all are unique => returning None
        LOG.debug(f'After refinement, current partition consists of {len(current_partition)} signal groups!')
    return current_partition


def find_matching_signals(vcd_filepaths: List[Union[Path, str]]) -> SIGNAL_GROUPS:
    """Finds signals in the given VCD files that always have the same value and groups them together.

    **The names of the top-level scopes (i.e. the testbench names) must match in all VCD files, otherwise grouping and matching will not work, as the root names would differ!**

    Args:
        vcd_filepaths: List of strings (paths to VCD files).

    Returns:
        List[List[str]]: List of lists of signal names that match perfectly in timing AND value.
    """
    current_partition = partition_all_vcd_signals(vcd_filepaths)

    # Filter out singletons (signals that match nothing), or return empty list if no partitioning happened (i.e. all signals are unique)
    return [group for group in current_partition if len(group) > 1] if current_partition is not None else []
