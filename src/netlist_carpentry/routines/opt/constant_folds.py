"""A collection of constant folding algorithms."""

from typing import Dict, List

from tqdm import tqdm

from netlist_carpentry import LOG, Instance, Module, Signal
from netlist_carpentry.core.exceptions import EvaluationError
from netlist_carpentry.core.netlist_elements.wire_segment import WireSegment
from netlist_carpentry.utils.gate_lib import DFF, DLatch
from netlist_carpentry.utils.gate_lib_base_classes import ClkMixin, EnMixin, PrimitiveGate, RstMixin


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
    """Executes a single iteration of the constant propagation algorithm for each instance of the given module.

    Args:
        module (Module): The module in which constants should be propagated.

    Returns:
        bool: True if at least one instance was removed due to constant propagation, False otherwise.
    """
    mark_delete: List[Instance] = []
    for inst in tqdm(module.instances.values(), leave=False):
        if getattr(inst, 'is_combinational', False):
            if _opt_constant_propagate_combinational(module, inst):
                mark_delete.append(inst)
        elif getattr(inst, 'is_sequential', False):
            if _opt_constant_propagate_sequential(module, inst):
                mark_delete.append(inst)
    for inst in mark_delete:
        module.remove_instance(inst)
    return bool(mark_delete)


def _propagate_output_port(module: Module, inst: PrimitiveGate, port_name: str, signals: Dict[int, Signal]) -> None:
    for idx, ps in inst.ports[port_name]:
        ws = ps.ws
        w = ws.parent
        for ld in ws.loads():
            module.disconnect(ld)
            ld.tie_signal(signals[idx])
        module.disconnect(ps)
        if not ws.port_segments:
            w.remove_wire_segment(ws.index)
        if not w.segments:
            module.remove_wire(w)


def _propagate_pass_wire(module: Module, inst: PrimitiveGate, port_name: str, wires: Dict[int, WireSegment]) -> None:
    for idx, ps in inst.ports[port_name]:
        ws = ps.ws
        w = ws.parent
        for ld in ws.loads():
            module.disconnect(ld)
            module.connect(wires[idx], ld)
        module.disconnect(ps)
        if not ws.port_segments:
            w.remove_wire_segment(ws.index)
        if not w.segments:
            module.remove_wire(w)


def _opt_constant_propagate_combinational(module: Module, inst: PrimitiveGate) -> bool:
    """Executes constant propagation for combinational instances.

    Args:
        module (Module): The module in which constants should be propagated.
        inst (PrimitiveGate): The combinational instance in question.

    Returns:
        bool: True, if the instance has constant inputs and can be simplified, False otherwise.
    """
    if all(p.is_tied_defined for p in inst.input_ports):
        try:
            inst.evaluate()
        except (EvaluationError, NotImplementedError) as e:
            LOG.warn(f'Unable to evaluate instance {inst.raw_path}: {e}!')
            return False
        for p in inst.output_ports:
            _propagate_output_port(module, inst, p.name, p.signal_array)
        return True
    return False


def _opt_constant_propagate_sequential(module: Module, inst: PrimitiveGate) -> bool:
    """Executes constant propagation for sequential instances.

    Args:
        module (Module): The module in which constants should be propagated.
        inst (PrimitiveGate): The sequential instance in question.

    Returns:
        bool: True, if the instance has constant inputs and can be simplified, False otherwise.
    """
    if isinstance(inst, DFF):
        return _opt_constant_propagate_dff(module, inst)
    if isinstance(inst, DLatch):
        return _opt_constant_propagate_dlatch(module, inst)
    LOG.warn(f'Cannot perform constant propagation for {inst.instance_type}!')
    return False


def _tied_rst_active(inst: RstMixin) -> bool:
    return inst.rst_port.is_tied_defined and inst.rst_polarity is inst.rst_port.signal


def _tied_clk(inst: ClkMixin) -> bool:
    return inst.clk_port.is_tied


def _tied_en_inactive(inst: EnMixin) -> bool:
    return inst.en_port.is_tied and inst.en_polarity is not inst.en_port.signal


def _opt_constant_propagate_dff(module: Module, inst: DFF) -> bool:
    # Order: Reset highest prio, then clk, then data
    ff_id = f'{inst.__class__.__name__} {inst.raw_path}'
    propagates = False
    if isinstance(inst, RstMixin):
        if _tied_rst_active(inst):  # Propagate, RST is constant and always in reset
            _propagate_output_port(module, inst, 'Q', inst.rst_val)  # Propagate reset value
            propagates = True
    if _tied_clk(inst):  # TODO: How can this case be simplified?
        LOG.warn(
            f"Found {ff_id} with tied Clock signal '{inst.clk_port.signal_str}' ({ff_id} never active, except for reset). Constant propagation not implemented for this edge case!"
        )
    if isinstance(inst, EnMixin):
        if _tied_en_inactive(inst):  # Never active
            LOG.warn(
                f'Found {ff_id} with disabled Enable signal ({ff_id} never active, except for reset). Constant propagation not implemented for this edge case!'
            )

    if inst.ports['D'].is_tied and not _tied_clk(inst) and not _tied_en_inactive(inst):
        _propagate_output_port(module, inst, 'Q', inst.ports['D'].signal_array)  # Propagate data to output
        propagates = True
    return propagates


def _opt_constant_propagate_dlatch(module: Module, inst: DLatch) -> bool:
    if inst.en_port.is_tied_defined:
        if inst.en_signal is inst.en_polarity:  # Always transparent -> Q === D
            _propagate_pass_wire(module, inst, 'Q', {idx: ps.ws for idx, ps in inst.ports['D']})
            return True
        else:  # Never transparent -> Q = x
            _propagate_output_port(module, inst, 'Q', {idx: Signal.UNDEFINED for idx in inst.ports['Q'].signal_array})
            return True
    return False
