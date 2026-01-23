"""A module to track fanout of all wires inside a module or the whole circuit."""

from collections import defaultdict
from typing import Dict, List, Literal, NoReturn, Union, overload

from pydantic import NonNegativeInt

from netlist_carpentry import Circuit, Module
from netlist_carpentry.core.exceptions import UnsupportedOperationError
from netlist_carpentry.core.netlist_elements.element_path import WirePath, WireSegmentPath

FANOUT_BY_NUMBER = Dict[NonNegativeInt, List[Union[WirePath, WireSegmentPath]]]
"""A fanout dictionary, where the keys are the fanout numbers, and the values are lists of wire (segment) paths, where the wire has a fanout count equal to the key."""
FANOUT_BY_PATH = Dict[Union[WirePath, WireSegmentPath], NonNegativeInt]
"""A fanout dictionary, where the keys are the wire (segment) paths, and the value is the fanout count."""


def _raise_unsupported_sort(sort_by: str) -> NoReturn:
    raise UnsupportedOperationError(f'Cannot sort fanout by {sort_by}!')


@overload
def fanout(circuit_or_module: Union[Circuit, Module], *, sort_by: Literal['number']) -> FANOUT_BY_NUMBER: ...
@overload
def fanout(circuit_or_module: Union[Circuit, Module], *, sort_by: Literal['path']) -> FANOUT_BY_PATH: ...
def fanout(circuit_or_module: Union[Circuit, Module], *, sort_by: Literal['number', 'path']) -> Union[FANOUT_BY_NUMBER, FANOUT_BY_PATH]:
    """Analyzes the fanout of the given module or circuit and returns a dictionary containing all wires and their fanout.

    If `circuit_or_module` is a module, analyze all wires within the given module.
    If `circuit_or_module` is a circuit, analyze all wires across the whole circuit.
    The dictionary will then contain the paths of all wires in the whole circuit.

    If `sort_by` is `'path'`, the keys of the returned dictionary are the wire paths,
    and the value is the fanout count. If this value is 0, the wire does not have any loads.
    If `sort_by` is `'number'`, the keys of the returned dictionary are the fanout numbers,
    and the value is a list of wire paths, where the wire has a fanout count equal to the key.
    All entries in the list for key 0 are wires without any loads.

    If a wire is more than 1 bit wide, and the segments have different fanout numbers,
    the wire segment paths are used (instead of the wire path) with the corresponding fanout numbers.

    Args:
        circuit_or_module (Union[Circuit, Module]): The module or whole circuit to analyze the fanout.
        sort_by (Literal[&#39;number&#39;, &#39;path&#39;]): Whether the fanout counts or the wire paths
            should be the keys of the returned fanout dictionary.

    Returns:
        Union[FANOUT_BY_NUMBER, FANOUT_BY_PATH]: A dictionary containing all wires and their fanout counts
            (if `sort_by` is `'path'`). Alternatively a dictionary of fanout numbers, where for each fanout number
            the value is a list of wire paths, where the wire has a fanout count equal to the key (if `sort_by` is `'number'`).
    """
    if isinstance(circuit_or_module, Circuit):
        if sort_by == 'path':
            return _fanout_circuit_path(circuit_or_module)
        elif sort_by == 'number':
            return _fanout_circuit_number(circuit_or_module)
        _raise_unsupported_sort(sort_by)
    return fanout_module(circuit_or_module, sort_by=sort_by)


def _fanout_circuit_path(circuit: Circuit) -> FANOUT_BY_PATH:
    fanout_dict = {}
    for m in circuit:
        fanout_dict.update(fanout(m, sort_by='path'))
    return fanout_dict


def _fanout_circuit_number(circuit: Circuit) -> FANOUT_BY_NUMBER:
    fanout_dict: FANOUT_BY_NUMBER = {}
    for m in circuit:
        m_fanout = fanout(m, sort_by='number')
        for idx in m_fanout:
            if idx not in fanout_dict:
                fanout_dict[idx] = []
            fanout_dict[idx].extend(m_fanout[idx])
    return fanout_dict


@overload
def fanout_module(module: Module, *, sort_by: Literal['number']) -> FANOUT_BY_NUMBER: ...
@overload
def fanout_module(module: Module, *, sort_by: Literal['path']) -> FANOUT_BY_PATH: ...
def fanout_module(module: Module, *, sort_by: Literal['number', 'path']) -> Union[FANOUT_BY_NUMBER, FANOUT_BY_PATH]:
    """Analyzes the fanout of the given module and returns a dictionary containing all wires and their fanout.

    If `sort_by` is `'path'`, the keys of the returned dictionary are the wire paths,
    and the value is the fanout count. If this value is 0, the wire does not have any loads.
    If `sort_by` is `'number'`, the keys of the returned dictionary are the fanout numbers,
    and the value is a list of wire paths, where the wire has a fanout count equal to the key.
    All entries in the list for key 0 are wires without any loads.

    If a wire is more than 1 bit wide, and the segments have different fanout numbers,
    the wire segment paths are used (instead of the wire path) with the corresponding fanout numbers.

    Args:
        module (Module): The module to analyze the fanout.
        sort_by (Literal[&#39;number&#39;, &#39;path&#39;]): Whether the fanout counts or the wire paths
            should be the keys of the returned fanout dictionary.

    Returns:
        Union[FANOUT_BY_NUMBER, FANOUT_BY_PATH]: A dictionary containing all wires and their fanout counts
            (if `sort_by` is `'path'`). Alternatively a dictionary of fanout numbers, where for each fanout number
            the value is a list of wire paths, where the wire has a fanout count equal to the key (if `sort_by` is `'number'`).
    """
    if sort_by == 'path':
        return fanout_by_path(module)
    elif sort_by == 'number':
        return fanout_by_number(module)
    _raise_unsupported_sort(sort_by)


def fanout_by_path(module: Module) -> FANOUT_BY_PATH:
    """Analyzes the fanout of the given module and returns a dictionary containing all wires and their fanout.

    The keys of the returned dictionary are the wire paths, and the value is the fanout count.
    If this value is 0, the wire does not have any loads.

    If a wire is more than 1 bit wide, and the segments have different fanout numbers,
    the wire segment paths are used (instead of the wire path) with the corresponding fanout numbers.

    Args:
        module (Module): The module to analyze the fanout.

    Returns:
        FANOUT_BY_PATH: A dictionary containing all wires and their fanout counts.
    """
    fanout_dict: FANOUT_BY_PATH = {}
    for w in module.wires.values():
        lds = w.loads()
        llen = len(lds[next(iter(lds))])
        # Check if all have equal amount of loads, no splitting necessary
        if all(len(pslist) == llen for _, pslist in lds.items()):
            fanout_dict[w.path] = llen
        else:  # At least one segment has a different amount of loads, splitting necessary
            for _, ws in w:
                fanout_dict[ws.path] = len(ws.loads())
    return fanout_dict


def fanout_by_number(module: Module) -> FANOUT_BY_NUMBER:
    """Analyzes the fanout of the given module and returns a dictionary containing all wires and their fanout.

    The keys of the returned dictionary are the fanout numbers, and the value
    is a list of wire paths, where the wire has a fanout count equal to the key.
    All entries in the list for key 0 are wires without any loads.

    If a wire is more than 1 bit wide, and the segments have different fanout numbers,
    the wire segment paths are used (instead of the wire path) with the corresponding fanout numbers.

    Args:
        module (Module): The module to analyze the fanout.

    Returns:
        FANOUT_BY_NUMBER: A dictionary of fanout numbers, where for each fanout number the value is a list
        of wire paths, where the wire has a fanout count equal to the key (if `sort_by` is `'number'`).
    """
    fanout_dict: FANOUT_BY_NUMBER = defaultdict(list)
    for w in module.wires.values():
        lds = w.loads()
        llen = len(lds[next(iter(lds))])
        # Check if all have equal amount of loads, no splitting necessary
        if all(len(pslist) == llen for _, pslist in lds.items()):
            fanout_dict[llen].append(w.path)
        else:  # At least one segment has a different amount of loads, splitting necessary
            for _, ws in w:
                fanout_dict[len(ws.loads())].append(ws.path)
    return fanout_dict
