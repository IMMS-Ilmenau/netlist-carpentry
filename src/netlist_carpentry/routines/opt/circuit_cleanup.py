"""Optimization Methods to remove empty or uninstantiated modules from circuit perspective (top abstraction layer)."""

from netlist_carpentry.core.circuit import Circuit


def clean_circuit(circuit: Circuit) -> bool:
    """Execute several optimization and cleanup tasks on the circuit, from a top-level POV.

    Currently, the only implemented optimization process removes all unused modules from the circuit.
    As a result, every module not instantiated anywhere in the circuit is removed.

    Args:
        circuit (Circuit): The circuit to optimize.

    Returns:
        bool: True if the circuit was modified as a result of the optimization processes, False otherwise.
    """
    any_cleaned = False
    while True:
        any_cleaned_this_iteration = clean_unused(circuit)
        any_cleaned |= any_cleaned_this_iteration
        if not any_cleaned_this_iteration:
            return any_cleaned


def clean_unused(circuit: Circuit) -> bool:
    """Removes all modules that are not instantiated anywhere (and thus considered unused) in the given circuit.

    Args:
        circuit (Circuit): The circuit to clean and optimize.

    Returns:
        bool: True if at least one unused module was found and subsequently removed, False otherwise.
    """
    any_cleaned = False
    while True:
        if not _clean_unused_single(circuit):
            break
        any_cleaned = True
    return any_cleaned


def _clean_unused_single(circuit: Circuit) -> bool:
    """A single iteration of the `clean_unused` process.

    Removed all modules that are *currently* unused.
    This might lead to more modules being unused, if one of the removed modules contained submodules.
    If such modules were only instantiated in a just removed module, they become unused as well.
    Accordingly, they will be removed in the subsequent iteration.

    Args:
        circuit (Circuit): The circuit, on which a single iteration will be executed.

    Returns:
        bool: True if at least one unused module was found and removed, False otherwise.
    """
    # Remove all modules that are 1. not the top module and 2. not instantiated anywhere in the circuit
    modules_to_remove = [m for m in circuit if (not circuit.has_top or m is not circuit.top) and not circuit.instances.get(m.name, [])]
    for m in modules_to_remove:
        circuit.remove_module(m)
    return bool(modules_to_remove)
