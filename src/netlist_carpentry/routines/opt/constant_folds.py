"""A collection of constant folding algorithms."""
# mypy: disable-error-code="unreachable"

from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Union

from tqdm import tqdm

from netlist_carpentry import LOG, Instance, Module, Signal, SignalArray
from netlist_carpentry.core.exceptions import EvaluationError
from netlist_carpentry.core.netlist_elements.port_segment import PortSegment
from netlist_carpentry.core.netlist_elements.wire_segment import WireSegment
from netlist_carpentry.utils.gate_lib import DFF, DLatch, NotGate
from netlist_carpentry.utils.gate_lib_base_classes import BinaryGate, NtoOneGate, PrimitiveGate
from netlist_carpentry.utils.gate_mixins import EnMixin, RstMixin


class _Act(Enum):
    PASS = auto()
    INVERT = auto()


_LOW, _HIGH = Signal.LOW, Signal.HIGH

_RULES: Dict[Tuple[str, Signal], Union[Signal, _Act]] = {
    ('§and', _LOW): _LOW,
    ('§and', _HIGH): _Act.PASS,
    ('§nand', _LOW): _HIGH,
    ('§nand', _HIGH): _Act.INVERT,
    ('§or', _HIGH): _HIGH,
    ('§or', _LOW): _Act.PASS,
    ('§nor', _HIGH): _LOW,
    ('§nor', _LOW): _Act.INVERT,
    ('§xor', _LOW): _Act.PASS,
    ('§xor', _HIGH): _Act.INVERT,
    ('§xnor', _LOW): _Act.INVERT,
    ('§xnor', _HIGH): _Act.PASS,
}
_RULE_TYPES = {gate_type for gate_type, _ in _RULES}

_Rule = Union[Signal, Tuple[_Act, PortSegment]]


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
    for inst in tqdm(list(module.instances.values()), leave=False):
        if isinstance(inst, PrimitiveGate):
            if getattr(inst, 'is_combinational', False):  # type: ignore[misc]
                if _opt_constant_propagate_combinational(module, inst):
                    mark_delete.append(inst)
            elif getattr(inst, 'is_sequential', False):  # type: ignore[misc]
                if _opt_constant_propagate_sequential(module, inst):
                    mark_delete.append(inst)
    for inst in mark_delete:
        module.remove_instance(inst)
    return bool(mark_delete)


def _propagate_output_port(module: Module, inst: PrimitiveGate, port_name: str, signals: SignalArray) -> None:
    for idx, ps in inst.ports[port_name]:
        if idx not in signals.signals or ps.is_unconnected:
            continue
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


def _propagate_pass_wire(module: Module, inst: PrimitiveGate, port_name: str, wires: Dict[int, Union[WireSegment, PortSegment]]) -> None:
    for idx, ps in inst.ports[port_name]:
        if idx not in wires or ps.is_unconnected:
            continue
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


def _bit_rule(inst: PrimitiveGate, idx: int) -> Optional[_Rule]:
    """Looks how output bit `idx` can be simplified or returns None if no rule was found."""
    if isinstance(inst, NtoOneGate):
        if not inst.s_port.is_tied_defined or inst.active_input is None:
            return None
        seg = inst.active_input[idx]
        return _Act.PASS, seg
    if isinstance(inst, BinaryGate) and inst.instance_type in _RULE_TYPES:
        if any(idx not in p.segments for p in inst.input_ports):
            return None
        a, b = (p[idx] for p in inst.input_ports)
        if a.is_tied != b.is_tied:
            tied, free = (a, b) if a.is_tied else (b, a)
            rule = _RULES.get((inst.instance_type, tied.signal))
            if isinstance(rule, _Act):
                return rule, free
            return rule
    return None


def _opt_constant_propagate_rules(module: Module, inst: PrimitiveGate) -> bool:
    """Simplifies an instance with partially constant inputs, if every output bit matches a known rule.

    Args:
        module (Module): The module in which constants should be propagated.
        inst (PrimitiveGate): The combinational instance.

    Returns:
        bool: True, if the instance was simplified, False otherwise.
    """
    rules: Dict[int, _Rule] = {}
    for idx, _ in inst.output_port:
        rule = _bit_rule(inst, idx)
        if rule is None:
            return False
        rules[idx] = rule
    consts: Dict[int, Signal] = {}
    wires: Dict[int, Union[WireSegment, PortSegment]] = {}
    for idx, rule in rules.items():
        if isinstance(rule, Signal):
            consts[idx] = rule
            continue
        act, seg = rule
        if act is _Act.PASS:
            wires[idx] = seg.ws
        else:
            inv = module.create_instance(NotGate, f'{inst.name}_inv{idx}')
            module.connect(seg.ws, inv.ports['A'][0])
            wires[idx] = inv.ports['Y'][0]
    _propagate_output_port(module, inst, inst.output_port.name, SignalArray(signals=consts))
    _propagate_pass_wire(module, inst, inst.output_port.name, wires)
    return True


def _opt_constant_propagate_combinational(module: Module, inst: PrimitiveGate) -> bool:
    """Executes constant propagation for combinational instances.

    An instance is simplified if all of its inputs are constant, or if its partially constant inputs match a known rule (see `_RULES`).

    Args:
        module (Module): The module in which constants should be propagated.
        inst (PrimitiveGate): The combinational instance in question.

    Returns:
        bool: True, if the instance has constant inputs and can be simplified, False otherwise.
    """
    if all(p.is_tied_defined for p in inst.input_ports):
        try:
            inst.evaluate()
        except (EvaluationError, NotImplementedError, ArithmeticError) as e:
            LOG.warn(f'Unable to evaluate instance {inst.raw_path}: {e}!')
            return False
        for p in inst.output_ports:
            _propagate_output_port(module, inst, p.name, p.signal_array)
        return True
    return _opt_constant_propagate_rules(module, inst)


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


def _opt_constant_propagate_dff(module: Module, inst: DFF) -> bool:
    # Order: Reset highest prio, then clk, then data
    ff_id = f'{inst.__class__.__name__} {inst.raw_path}'
    if inst.has_rst and isinstance(inst, RstMixin):
        # Propagate, RST is constant and always in reset
        if inst.ports['RST'].is_tied_defined and inst.rst_polarity is inst.ports['RST'].signal:
            _propagate_output_port(module, inst, 'Q', inst.rst_val)  # Propagate reset value
            return True
    if inst.ports['CLK'].is_tied:  # TODO: How can this case be simplified?
        warn_str = f"Found {ff_id} with tied Clock signal '{inst.ports['CLK'].signal_str}' ({ff_id} never active, except for reset). Constant propagation not implemented for this edge case!"
        LOG.warn(warn_str)
    if isinstance(inst, EnMixin):
        # Never active
        if inst.en_port.is_tied and inst.en_polarity is not inst.en_port.signal:
            warn_str = (
                f'Found {ff_id} with disabled Enable signal ({ff_id} never active, except for reset). Constant propagation not implemented for this edge case!'
            )
            LOG.warn(warn_str)

    if inst.ports['D'].is_tied and not inst.ports['CLK'].is_tied:
        if not isinstance(inst, EnMixin) or (inst.en_port.is_tied and inst.en_polarity is inst.en_port.signal):  # No EN, or tied EN active
            _propagate_output_port(module, inst, 'Q', inst.ports['D'].signal_array)  # Propagate data to output
            return True
    return False


def _opt_constant_propagate_dlatch(module: Module, inst: DLatch) -> bool:
    if inst.en_port.is_tied_defined:
        if inst.en_signal is inst.en_polarity:  # Always transparent -> Q === D
            _propagate_pass_wire(module, inst, 'Q', {idx: ps.ws for idx, ps in inst.ports['D']})
            return True
        else:  # Never transparent -> Q = x
            _propagate_output_port(module, inst, 'Q', SignalArray(signals={idx: Signal.UNDEFINED for idx in inst.ports['Q'].signal_array}))
            return True
    return False
