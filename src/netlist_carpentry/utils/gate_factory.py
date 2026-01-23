"""Factory methods simplifying instantiation of primitive gates, based on the classes from the gate library."""

from math import ceil, log2
from typing import Dict, List, Optional, Tuple, Type, TypeVar, Union

import netlist_carpentry.utils.gate_lib as g
from netlist_carpentry.core.exceptions import MultipleDriverError, WidthMismatchError
from netlist_carpentry.core.netlist_elements.instance import Instance
from netlist_carpentry.core.netlist_elements.module import Module as M
from netlist_carpentry.core.netlist_elements.port import Port
from netlist_carpentry.utils.gate_lib_base_classes import PrimitiveGate
from netlist_carpentry.utils.log import LOG

GATE = TypeVar('GATE', bound=PrimitiveGate)
PORT = Union[Port[M], Port[Instance]]


def _check_out_connection(port: Optional[PORT], inst: Instance) -> None:
    if port is not None and port.is_driver:
        raise MultipleDriverError(
            f'Unable to instantiate {inst.__class__.__name__} {inst.raw_path}: '
            + f'Expected port {port.raw_path} to be a load port, but got a driver instead!'
        )


def _update_params(params: Dict[str, object], ports: List[Optional[PORT]], key: str = 'Y_WIDTH') -> None:
    _check_width_mismatch(params, ports)
    if any(p is not None for p in ports) or key not in params:
        # Extract the width from the provided ports (if present)
        # If no ports are present and params does not contain "Y_WIDTH", set it to its default value 1
        params.update({key: _get_width(ports)})


def _get_width(ports: List[Optional[PORT]]) -> int:
    """
    Retrieve the bit width common to all given ports.

    Ensures that all ports in the provided list have the same bit width.
    If a mismatch is detected, a WidthMismatchError is raised with detailed
    information about each port's path and width.

    Args:
        ports (List[Port]): A list of Port objects whose widths are to be checked.

    Returns:
        int: The common bit width of all ports, or `1` if the list is empty.

    Raises:
        WidthMismatchError: If the ports do not all share the same width.
    """
    filtered_ports = [p for p in ports if p is not None]
    if not all(p.width == filtered_ports[0].width for p in filtered_ports):
        raise WidthMismatchError(
            'The ports to which the instance is to be connected have different widths:'
            + ''.join(f'\n\t{p.raw_path} -> {p.width} bit(s)' for p in filtered_ports)
        )
    return filtered_ports[0].width if filtered_ports else 1


def _check_width_mismatch(params: Dict[str, object], ports: List[Optional[PORT]], key: str = 'Y_WIDTH') -> None:
    if key in params:
        for p in ports:
            if p is not None and p.width != params[key]:
                raise WidthMismatchError(
                    f'Found a width value in the parameter dictionary ({params[key]}), which does not match the width of the given port {p.raw_path} ({p.width})!'
                )


def _un_gate(
    gate: Type[GATE],
    module: M,
    inst_name: Optional[str] = None,
    A: Optional[PORT] = None,
    Y: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> GATE:
    params = params or {}
    _update_params(params, [A, Y])
    g = module.create_instance(gate, inst_name, params)
    _check_out_connection(Y, g)
    if A is not None:
        module.connect(A, g.ports['A'])
    if Y is not None:
        module.connect(g.ports['Y'], Y)
    return g


def buffer(
    module: M, inst_name: Optional[str] = None, A: Optional[PORT] = None, Y: Optional[PORT] = None, params: Optional[Dict[str, object]] = None
) -> g.Buffer:
    return _un_gate(g.Buffer, module, inst_name, A, Y, params)


def not_gate(
    module: M, inst_name: Optional[str] = None, A: Optional[PORT] = None, Y: Optional[PORT] = None, params: Optional[Dict[str, object]] = None
) -> g.NotGate:
    return _un_gate(g.NotGate, module, inst_name, A, Y, params)


def neg_gate(
    module: M, inst_name: Optional[str] = None, A: Optional[PORT] = None, Y: Optional[PORT] = None, params: Optional[Dict[str, object]] = None
) -> g.NegGate:
    return _un_gate(g.NegGate, module, inst_name, A, Y, params)


def _reduce_gate(
    gate: Type[GATE],
    module: M,
    inst_name: Optional[str] = None,
    A: Optional[PORT] = None,
    Y: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> GATE:
    params = params or {}
    _update_params(params, [A], 'A_WIDTH')
    g = module.create_instance(gate, inst_name, params)
    _check_out_connection(Y, g)
    if A is not None:
        module.connect(A, g.ports['A'])
    if Y is not None:
        if Y.width != 1:
            raise WidthMismatchError(
                f'Cannot connect {Y.raw_path} to {g.raw_path}: Reduction gates produce a 1-bit wide signal, but {Y.raw_path} is {Y.width} bits wide.'
            )
        module.connect(g.ports['Y'], Y)
    return g


def reduce_and(
    module: M, inst_name: Optional[str] = None, A: Optional[PORT] = None, Y: Optional[PORT] = None, params: Optional[Dict[str, object]] = None
) -> g.ReduceAnd:
    return _reduce_gate(g.ReduceAnd, module, inst_name, A, Y, params)


def reduce_or(
    module: M, inst_name: Optional[str] = None, A: Optional[PORT] = None, Y: Optional[PORT] = None, params: Optional[Dict[str, object]] = None
) -> g.ReduceOr:
    return _reduce_gate(g.ReduceOr, module, inst_name, A, Y, params)


def reduce_bool(
    module: M, inst_name: Optional[str] = None, A: Optional[PORT] = None, Y: Optional[PORT] = None, params: Optional[Dict[str, object]] = None
) -> g.ReduceBool:
    return _reduce_gate(g.ReduceBool, module, inst_name, A, Y, params)


def reduce_xor(
    module: M, inst_name: Optional[str] = None, A: Optional[PORT] = None, Y: Optional[PORT] = None, params: Optional[Dict[str, object]] = None
) -> g.ReduceXor:
    return _reduce_gate(g.ReduceXor, module, inst_name, A, Y, params)


def reduce_xnor(
    module: M, inst_name: Optional[str] = None, A: Optional[PORT] = None, Y: Optional[PORT] = None, params: Optional[Dict[str, object]] = None
) -> g.ReduceXnor:
    return _reduce_gate(g.ReduceXnor, module, inst_name, A, Y, params)


def logic_not(
    module: M, inst_name: Optional[str] = None, A: Optional[PORT] = None, Y: Optional[PORT] = None, params: Optional[Dict[str, object]] = None
) -> g.LogicNot:
    return _reduce_gate(g.LogicNot, module, inst_name, A, Y, params)


def _bin_gate(
    gate: Type[GATE],
    module: M,
    inst_name: Optional[str] = None,
    A: Optional[PORT] = None,
    B: Optional[PORT] = None,
    Y: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> GATE:
    params = params or {}
    _update_params(params, [A, B, Y])
    g = module.create_instance(gate, inst_name, params)
    _check_out_connection(Y, g)
    if A is not None:
        module.connect(A, g.ports['A'])
    if B is not None:
        module.connect(B, g.ports['B'])
    if Y is not None:
        module.connect(g.ports['Y'], Y)
    return g


def and_gate(
    module: M,
    inst_name: Optional[str] = None,
    A: Optional[PORT] = None,
    B: Optional[PORT] = None,
    Y: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> g.AndGate:
    return _bin_gate(g.AndGate, module, inst_name, A, B, Y, params)


def or_gate(
    module: M,
    inst_name: Optional[str] = None,
    A: Optional[PORT] = None,
    B: Optional[PORT] = None,
    Y: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> g.OrGate:
    return _bin_gate(g.OrGate, module, inst_name, A, B, Y, params)


def xor_gate(
    module: M,
    inst_name: Optional[str] = None,
    A: Optional[PORT] = None,
    B: Optional[PORT] = None,
    Y: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> g.XorGate:
    return _bin_gate(g.XorGate, module, inst_name, A, B, Y, params)


def xnor_gate(
    module: M,
    inst_name: Optional[str] = None,
    A: Optional[PORT] = None,
    B: Optional[PORT] = None,
    Y: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> g.XnorGate:
    return _bin_gate(g.XnorGate, module, inst_name, A, B, Y, params)


def nor_gate(
    module: M,
    inst_name: Optional[str] = None,
    A: Optional[PORT] = None,
    B: Optional[PORT] = None,
    Y: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> g.NorGate:
    return _bin_gate(g.NorGate, module, inst_name, A, B, Y, params)


def nand_gate(
    module: M,
    inst_name: Optional[str] = None,
    A: Optional[PORT] = None,
    B: Optional[PORT] = None,
    Y: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> g.NandGate:
    return _bin_gate(g.NandGate, module, inst_name, A, B, Y, params)


def _shift_gate(
    gate: Type[GATE],
    module: M,
    inst_name: Optional[str] = None,
    A: Optional[PORT] = None,
    B: Optional[PORT] = None,
    Y: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> GATE:
    params = params or {}
    _update_params(params, [A, Y])
    g = module.create_instance(gate, inst_name, params)
    _check_out_connection(Y, g)
    if A is not None:
        module.connect(A, g.ports['A'])
    if B is not None:
        if A is not None and B.width > ceil(log2(A.width)):  # TODO maybe move this check to shift gate instantiation method
            LOG.warn(f'Shift amount port "B" is {B.width} bits wide, but only {ceil(log2(A.width))} bits are meaningful for {A.width}-bit data.')
        g.ports['B'].segments.clear()
        g.ports['B'].create_port_segments(B.width)
        module.connect(B, g.ports['B'])
    if Y is not None:
        module.connect(g.ports['Y'], Y)
    return g


def shift_signed(
    module: M,
    inst_name: Optional[str] = None,
    A: Optional[PORT] = None,
    B: Optional[PORT] = None,
    Y: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> g.ShiftSigned:
    return _shift_gate(g.ShiftSigned, module, inst_name, A, B, Y, params)


def shift_left(
    module: M,
    inst_name: Optional[str] = None,
    A: Optional[PORT] = None,
    B: Optional[PORT] = None,
    Y: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> g.ShiftLeft:
    return _shift_gate(g.ShiftLeft, module, inst_name, A, B, Y, params)


def shift_right(
    module: M,
    inst_name: Optional[str] = None,
    A: Optional[PORT] = None,
    B: Optional[PORT] = None,
    Y: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> g.ShiftRight:
    return _shift_gate(g.ShiftRight, module, inst_name, A, B, Y, params)


def _binNto1_gate(
    gate: Type[GATE],
    module: M,
    inst_name: Optional[str] = None,
    A: Optional[PORT] = None,
    B: Optional[PORT] = None,
    Y: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> GATE:
    params = params or {}
    _update_params(params, [A, B], 'A_WIDTH')
    g = module.create_instance(gate, inst_name, params)
    _check_out_connection(Y, g)
    if A is not None:
        module.connect(A, g.ports['A'])
    if B is not None:
        module.connect(B, g.ports['B'])
    if Y is not None:
        if Y.width != 1:
            raise WidthMismatchError(
                f'Cannot connect {Y.raw_path} to {g.raw_path}: Reduction gates produce a 1-bit wide signal, but {Y.raw_path} is {Y.width} bits wide.'
            )
        module.connect(g.ports['Y'], Y)
    return g


def logic_and(
    module: M,
    inst_name: Optional[str] = None,
    A: Optional[PORT] = None,
    B: Optional[PORT] = None,
    Y: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> g.LogicAnd:
    return _binNto1_gate(g.LogicAnd, module, inst_name, A, B, Y, params)


def logic_or(
    module: M,
    inst_name: Optional[str] = None,
    A: Optional[PORT] = None,
    B: Optional[PORT] = None,
    Y: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> g.LogicOr:
    return _binNto1_gate(g.LogicOr, module, inst_name, A, B, Y, params)


def less_than(
    module: M,
    inst_name: Optional[str] = None,
    A: Optional[PORT] = None,
    B: Optional[PORT] = None,
    Y: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> g.LessThan:
    return _binNto1_gate(g.LessThan, module, inst_name, A, B, Y, params)


def less_equal(
    module: M,
    inst_name: Optional[str] = None,
    A: Optional[PORT] = None,
    B: Optional[PORT] = None,
    Y: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> g.LessEqual:
    return _binNto1_gate(g.LessEqual, module, inst_name, A, B, Y, params)


def equal(
    module: M,
    inst_name: Optional[str] = None,
    A: Optional[PORT] = None,
    B: Optional[PORT] = None,
    Y: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> g.Equal:
    return _binNto1_gate(g.Equal, module, inst_name, A, B, Y, params)


def not_equal(
    module: M,
    inst_name: Optional[str] = None,
    A: Optional[PORT] = None,
    B: Optional[PORT] = None,
    Y: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> g.NotEqual:
    return _binNto1_gate(g.NotEqual, module, inst_name, A, B, Y, params)


def greater_than(
    module: M,
    inst_name: Optional[str] = None,
    A: Optional[PORT] = None,
    B: Optional[PORT] = None,
    Y: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> g.GreaterThan:
    return _binNto1_gate(g.GreaterThan, module, inst_name, A, B, Y, params)


def greater_equal(
    module: M,
    inst_name: Optional[str] = None,
    A: Optional[PORT] = None,
    B: Optional[PORT] = None,
    Y: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> g.GreaterEqual:
    return _binNto1_gate(g.GreaterEqual, module, inst_name, A, B, Y, params)


def multiplexer(
    module: M,
    inst_name: Optional[str] = None,
    D_ports: List[Optional[PORT]] = [],
    S: Optional[PORT] = None,
    Y: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> g.Multiplexer:
    if S and S.width != ceil(log2(len(D_ports))):
        raise WidthMismatchError(
            f'Number of D ports does not match the width of the select port of mux {inst_name} in module {module.raw_path}: '
            + f'{len(D_ports)} D ports, but S is {S.width} bit wide!'
        )
    params = params or {}
    _update_params(params, [*D_ports, Y], 'WIDTH')
    params.update({'BIT_WIDTH': _get_width([S])})
    gate = module.create_instance(g.Multiplexer, inst_name, params)
    _check_out_connection(Y, gate)
    for i, D in enumerate(D_ports):
        if D is not None:
            module.connect(D, gate.ports[f'D{i}'])
    if S is not None:
        module.connect(S, gate.ports['S'])
    if Y is not None:
        module.connect(gate.ports['Y'], Y)
    return gate


def demultiplexer(
    module: M,
    inst_name: Optional[str] = None,
    D: Optional[PORT] = None,
    S: Optional[PORT] = None,
    Y_ports: List[Optional[PORT]] = [],
    params: Optional[Dict[str, object]] = None,
) -> g.Demultiplexer:
    if S and S.width != ceil(log2(len(Y_ports))):
        raise WidthMismatchError(
            f'Number of Y ports does not match the width of the select port of demux {inst_name} in module {module.raw_path}: '
            + f'{len(Y_ports)} Y ports, but S is {S.width} bit wide!'
        )
    params = params or {}
    _update_params(params, [*Y_ports, D], 'WIDTH')
    params.update({'BIT_WIDTH': _get_width([S])})
    gate = module.create_instance(g.Demultiplexer, inst_name, params)
    if D is not None:
        module.connect(D, gate.ports['D'])
    if S is not None:
        module.connect(S, gate.ports['S'])
    for i, Y in enumerate(Y_ports):
        _check_out_connection(Y, gate)
        if Y is not None:
            module.connect(gate.ports[f'Y{i}'], Y)
    return gate


### ARITHMETIC GATES !!!


def _dff(
    gate: Type[GATE],
    module: M,
    inst_name: Optional[str] = None,
    D: Optional[PORT] = None,
    ctrl_ports: List[Tuple[str, Optional[PORT]]] = [],
    Q: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> GATE:
    params = params or {}
    _update_params(params, [D, Q], key='WIDTH')
    dff = module.create_instance(gate, inst_name, params)
    _check_out_connection(Q, dff)
    if D is not None:
        module.connect(D, dff.ports['D'])
    for cn, cp in ctrl_ports:
        if cp is not None:
            if cp.width != 1:
                raise WidthMismatchError(
                    f'Cannot connect {cp.raw_path} to {cn} port of DFF {dff.raw_path}: {cn} signal must be 1 bit, but {cp.raw_path} is {cp.width} bits wide.'
                )
            module.connect(cp, dff.ports[cn])
    if Q is not None:
        module.connect(dff.ports['Q'], Q)
    return dff


def dff(
    module: M,
    inst_name: Optional[str] = None,
    D: Optional[PORT] = None,
    CLK: Optional[PORT] = None,
    Q: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> g.DFF:
    return _dff(g.DFF, module, inst_name, D, [('CLK', CLK)], Q, params)


def adff(
    module: M,
    inst_name: Optional[str] = None,
    D: Optional[PORT] = None,
    CLK: Optional[PORT] = None,
    RST: Optional[PORT] = None,
    Q: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> g.ADFF:
    return _dff(g.ADFF, module, inst_name, D, [('CLK', CLK), ('RST', RST)], Q, params)


def dffe(
    module: M,
    inst_name: Optional[str] = None,
    D: Optional[PORT] = None,
    CLK: Optional[PORT] = None,
    EN: Optional[PORT] = None,
    Q: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> g.DFFE:
    return _dff(g.DFFE, module, inst_name, D, [('CLK', CLK), ('EN', EN)], Q, params)


def adffe(
    module: M,
    inst_name: Optional[str] = None,
    D: Optional[PORT] = None,
    CLK: Optional[PORT] = None,
    RST: Optional[PORT] = None,
    EN: Optional[PORT] = None,
    Q: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> g.ADFFE:
    return _dff(g.ADFFE, module, inst_name, D, [('CLK', CLK), ('RST', RST), ('EN', EN)], Q, params)


def _scan_dff(
    gate: Type[GATE],
    module: M,
    inst_name: Optional[str] = None,
    D: Optional[PORT] = None,
    SI: Optional[PORT] = None,
    ctrl_ports: List[Tuple[str, Optional[PORT]]] = [],
    Q: Optional[PORT] = None,
    SO: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> GATE:
    dff = _dff(gate, module, inst_name, D, ctrl_ports, Q, params)
    params = params or {}
    _update_params(params, [SI, SO])
    _check_out_connection(SO, dff)
    if SI is not None:
        module.connect(SI, dff.ports['SI'])
    if SO is not None:
        module.connect(dff.ports['SO'], SO)
    return dff


def scan_dff(
    module: M,
    inst_name: Optional[str] = None,
    D: Optional[PORT] = None,
    SI: Optional[PORT] = None,
    SE: Optional[PORT] = None,
    CLK: Optional[PORT] = None,
    Q: Optional[PORT] = None,
    SO: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> g.ScanDFF:
    return _scan_dff(g.ScanDFF, module, inst_name, D, SI, [('CLK', CLK), ('SE', SE)], Q, SO, params)


def scan_adff(
    module: M,
    inst_name: Optional[str] = None,
    D: Optional[PORT] = None,
    SI: Optional[PORT] = None,
    SE: Optional[PORT] = None,
    CLK: Optional[PORT] = None,
    RST: Optional[PORT] = None,
    Q: Optional[PORT] = None,
    SO: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> g.ScanADFF:
    return _scan_dff(g.ScanADFF, module, inst_name, D, SI, [('CLK', CLK), ('RST', RST), ('SE', SE)], Q, SO, params)


def scan_dffe(
    module: M,
    inst_name: Optional[str] = None,
    D: Optional[PORT] = None,
    SI: Optional[PORT] = None,
    SE: Optional[PORT] = None,
    CLK: Optional[PORT] = None,
    EN: Optional[PORT] = None,
    Q: Optional[PORT] = None,
    SO: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> g.ScanDFFE:
    return _scan_dff(g.ScanDFFE, module, inst_name, D, SI, [('CLK', CLK), ('EN', EN), ('SE', SE)], Q, SO, params)


def scan_adffe(
    module: M,
    inst_name: Optional[str] = None,
    D: Optional[PORT] = None,
    SI: Optional[PORT] = None,
    SE: Optional[PORT] = None,
    CLK: Optional[PORT] = None,
    RST: Optional[PORT] = None,
    EN: Optional[PORT] = None,
    Q: Optional[PORT] = None,
    SO: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> g.ScanADFFE:
    return _scan_dff(g.ScanADFFE, module, inst_name, D, SI, [('CLK', CLK), ('RST', RST), ('EN', EN), ('SE', SE)], Q, SO, params)


def dlatch(
    module: M,
    inst_name: Optional[str] = None,
    D: Optional[PORT] = None,
    EN: Optional[PORT] = None,
    Q: Optional[PORT] = None,
    params: Optional[Dict[str, object]] = None,
) -> g.DLatch:
    params = params or {}
    _update_params(params, [D, Q], key='WIDTH')
    dlatch = module.create_instance(g.DLatch, inst_name, params)
    _check_out_connection(Q, dlatch)
    if D is not None:
        module.connect(D, dlatch.ports['D'])
    if EN is not None:
        if EN.width != 1:
            raise WidthMismatchError(
                f'Cannot connect {EN.raw_path} to EN port of DFF {dlatch.raw_path}: EN signal must be 1 bit, but {EN.raw_path} is {EN.width} bits wide.'
            )
        module.connect(EN, dlatch.ports['EN'])
    if Q is not None:
        module.connect(dlatch.ports['Q'], Q)
    return dlatch
