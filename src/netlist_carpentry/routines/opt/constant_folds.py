"""A collection of constant folding algorithms."""

from typing import List

from tqdm import tqdm

from netlist_carpentry.core.exceptions import EvaluationError
from netlist_carpentry.core.netlist_elements.instance import Instance
from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.utils.log import LOG


def opt_constant(module: Module) -> bool:
    """Executes several optimization routines on the given module.

    These routines currently include constant propagation and constant multiplexer replacement.
    More passes may follow in the future

    Args:
        module (Module): The module to be optimized.

    Returns:
        bool: True if any optimizations were executed, False otherwise.
    """
    any_removed = False
    while True:
        any_removed_this_iteration = opt_constant_mux_inputs(module)
        any_removed_this_iteration |= opt_constant_propagation(module)
        any_removed |= any_removed_this_iteration
        if not any_removed_this_iteration:
            return any_removed


def opt_constant_mux_inputs(module: Module) -> bool:
    """Optimizes multiplexers, where both inputs are constant, by replacing them with the appropriate constant signal.

    If both inputs are constant and equal, the output is equal to the constant input.
    If both inputs are constant and unequal (i.e. one is 0 and one is 1), the output is either
    equal to `S` or `!S`, depending on which input is 0 and which is 1.
    If `S` is constant, the instance can be removed, since the output follows the corresponding input signal.

    Args:
        module (Module): The module in which constant multiplexers should be optimized.

    Returns:
        bool: True if any optimizations were executed.
            False if this module is already optimized in regards to constant multiplexers.
    """
    inst_to_remove: List[Instance] = []

    for inst in tqdm(module.instances.values(), leave=False):
        if inst.instance_type == '§mux':
            D0 = inst.connection_str_paths['D0'].values()
            D1 = inst.connection_str_paths['D1'].values()

            if all(i == '0' for i in D0) and all(i == '1' for i in D1):
                for j in inst.connections['Y']:
                    output_signal = module.get_from_path(inst.connections['Y'][j])  # PortSegment

                    for load in output_signal.loads():
                        module.disconnect(load)
                        module.connect(inst.connections['S'][0], load)

                inst_to_remove.append(inst)

    for inst in inst_to_remove:
        module.remove_instance(inst)

    return inst_to_remove != []


def opt_constant_propagation(module: Module) -> bool:
    """Executes constant propagation to simplify the circuit.

    Constant propagation replaces expressions with known constant values.
    By substituting constants it simplifies expressions, exposes dead instances and other optimization opportunities, and can reduce circuit size.
    For example, if the framework knows `A = 0` and later sees `B = A && 1`, it can replace B with 0 and eliminate the original assignment,
    since this expression can never be 1, as A is known to be 0, and `0 && x` is always 0.

    Args:
        module (Module): The module to perform constant propagation in

    Returns:
        bool: True if any optimizations were executed.
            False if this module is already optimized in regards to constant propagation.
    """
    any_propagated = False
    while True:
        now_propagated = _opt_constant_propagation_single_iter(module)
        any_propagated |= now_propagated
        if not now_propagated:
            break
    return any_propagated


def _opt_constant_propagation_single_iter(module: Module) -> bool:
    mark_delete: List[Instance] = []
    for inst in tqdm(module.instances.values(), leave=False):
        if all(p.is_tied_defined for p in inst.input_ports):
            try:
                inst.evaluate()
            except EvaluationError as e:
                LOG.warn(f'Unable to evaluate instance {inst.raw_path}: {e}!')
                continue
            mark_delete.append(inst)
            for p in inst.output_ports:
                for idx, ps in p:
                    out_signal = ps.signal
                    ws = ps.ws
                    w = ws.parent
                    for ld in ws.loads():
                        module.disconnect(ld)
                        ld.tie_signal(out_signal)
                    module.disconnect(ps)
                    if not ws.port_segments:
                        w.remove_wire_segment(ws.index)
                    if not w.segments:
                        module.remove_wire(w)
    for inst in mark_delete:
        module.remove_instance(inst)
    return bool(mark_delete)
