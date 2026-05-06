# mypy: disable-error-code="typeddict-item"
"""
This module provides a set of classes for modeling digital circuits at the gate level.
It currently includes base classes for primitive gates, unary gates, binary gates, and clocked gates,
as well as methods for evaluating the output signals of these gates.
They provide a common interface for working with different types of gates,
including methods for setting input signals, evaluating output signals, and updating gate states.
See the gate_lib.py module for further information.
"""

import warnings
from typing import Dict, Iterable, List, Literal, Optional, Tuple

from pydantic import BaseModel, NonNegativeInt, PositiveInt
from typing_extensions import Self

from netlist_carpentry import CFG, LOG, Direction, Instance, Module, Port, Signal
from netlist_carpentry.core.exceptions import EvaluationError, WidthMismatchError
from netlist_carpentry.core.netlist_elements.port import ANY_PORT
from netlist_carpentry.core.netlist_elements.wire_segment import CONST_MAP_VAL2OBJ, WIRE_SEGMENT_X, WireSegment
from netlist_carpentry.core.protocols.signals import SignalOrLogicLevel
from netlist_carpentry.utils.gate_lib_dataclasses import (
    BinaryParams,
    DFFParams,
    GateParams,
    Parameters,
    UnaryParams,
)
from netlist_carpentry.utils.safe_format_dict import SafeFormatDict


class PrimitiveGate(Instance, BaseModel):
    """
    A base class for all primitive gates.

    Primitive gates are the basic building blocks of digital circuits, and they can be combined to create more complex circuits.
    This class provides a common interface for all primitive gates, including methods for evaluating the gate's output and setting its output signal.
    """

    instance_type: str = CFG.id_internal
    """Identifier for instances of this gate type."""

    parameters: GateParams = GateParams()
    """Parameters of this gate, e.g. data width, signedness or polarity."""

    @property
    def y_width(self) -> PositiveInt:
        """Width of the gate, based on a certain port's width, depending on the actual gate."""
        warnings.warn(
            f'{self.__class__.__name__}.y_width is deprecated and will be removed in v1.0.0. If applicable, use {self.__class__.__name__}.data_width instead, or retrieve the width via {self.__class__.__name__}.ports[port_name].width!',
            DeprecationWarning,
            stacklevel=2,
        )
        self._try_sync_parameters()
        return int(self.parameters.Y_WIDTH) if hasattr(self.parameters, 'Y_WIDTH') else 1  # type: ignore[misc]

    @property
    def a_width(self) -> PositiveInt:
        """Width of the gate's `A` port."""
        warnings.warn(
            f'{self.__class__.__name__}.a_width is deprecated and will be removed in v1.0.0. If applicable, use {self.__class__.__name__}.data_width instead, or retrieve the width via {self.__class__.__name__}.ports[port_name].width!',
            DeprecationWarning,
            stacklevel=2,
        )
        self._try_sync_parameters()
        return int(self.parameters.A_WIDTH) if hasattr(self.parameters, 'A_WIDTH') else self.y_width  # type: ignore[misc]

    @property
    def b_width(self) -> PositiveInt:
        """Width of the gate's `B` port."""
        warnings.warn(
            f'{self.__class__.__name__}.b_width is deprecated and will be removed in v1.0.0. If applicable, use {self.__class__.__name__}.data_width instead, or retrieve the width via {self.__class__.__name__}.ports[port_name].width!',
            DeprecationWarning,
            stacklevel=2,
        )
        self._try_sync_parameters()
        return int(self.parameters.B_WIDTH) if hasattr(self.parameters, 'B_WIDTH') else self.y_width  # type: ignore[misc]

    @property
    def is_combinational(self) -> bool:
        """Whether instances of this gate are considered combinational gates.

        `True` for combinational gates, such as AND gates or arithmetic gates.
        `False` for flip-flops and latches.
        """
        return True

    @property
    def is_sequential(self) -> bool:
        """Whether instances of this gate are considered sequential gates.

        `False` for combinational gates, such as AND gates or arithmetic gates.
        `True` for flip-flops and latches.
        """
        return not self.is_combinational

    @property
    def output_port(self) -> Port[Instance]:
        """The output port of the gate."""
        raise NotImplementedError(f'Not implemented in base class {self.__class__.__name__}!')

    @property
    def is_primitive(self) -> bool:
        return True

    @property
    def is_module_instance(self) -> bool:
        return False

    @property
    def data_width(self) -> int:
        """
        The data width of this instance.

        Defaults to the data width of the output port.
        Can be overwritten in extended classes.

        In contrast to `self.width`, which is used for the creation and initialization,
        this property is linked to the data width of the output port.
        This property is useful when the data width of the output port can be changed.
        """
        return self.output_port.width

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1};'

    @property
    def verilog_net_map(self) -> Dict[str, str]:
        """The parts of the Verilog representation of this gate instance as a dict.

        If this gate is an AND gate, and the Verilog representation of this gate would be `assign wire_out = wire1 & wire2;`,
        then this dict is:
        ```python
        {
            "Y": "wire_out",
            "A": "wire1",
            "B": "wire2",
        }
        ```
        """
        return {}

    def _try_sync_parameters(self) -> None:
        try:
            self.sync_parameters(False)
        except KeyError:  # Happens during initialization phase, where ports do not have a width yet
            pass

    def sync_parameters(self, warn: bool = True) -> Optional[Parameters]:
        if warn:
            warnings.warn(
                f'The return value {self.__class__.__name__}.sync_parameters() will be `None` starting from version 1.0.0. '
                + f'To retrieve the parameters, please use {self.__class__.__name__}.parameters after calling {self.__class__.__name__}.sync_parameters()! '
                + f'You can silence this warning with `{self.__class__.__name__}.sync_parameters(warn=False)`.',
                FutureWarning,
                stacklevel=2,
            )
        return self.parameters

    def p2v(self, port: ANY_PORT, exclude_indices: Optional[List[int]] = None) -> str:
        """
        Converts a Port object to its corresponding Verilog structure by using the connected wire segments.

        This method takes the connected wire segments of a Port object and converts them to their corresponding
        Verilog signal structure (p2ws2v -> Port to WireSegment to Verilog signal syntax).
        The method requires that the currently selected module matches the module of the Port object,
        which is derived from the design path of the Port object.
        For each segment of the port, it checks whether a corresponding connected wire segment exists in the current module.
        If the port is set to a constant, the corresponding constant wire segment placeholder is used instead.
        Port segments can be excluded from the conversion by providing a list of indices,
        indicating which segments should be excluded from the conversion (e.g. segments that are known to be unconnected).

        Args:
            port (Port): The Port object to convert.
            exclude_indices (List[int], optional): A list of indices to exclude from the conversion. Defaults to an empty list.

        Returns:
            str: The Verilog signal structure as a string.

        Raises:
            AttributeError: If the currently selected module does not match the module of the port.
        """
        from netlist_carpentry.io.write.py2v import P2VTransformer as P2V

        if exclude_indices is None:
            exclude_indices = []
        curr_module: Module = port.module
        wsegs: List[WireSegment] = []
        for idx, ps in reversed(port.segments.items()):
            if idx not in exclude_indices:
                if not ps.is_tied:
                    ws = curr_module.get_from_path(ps.ws_path)
                    if ws is not None:
                        wsegs.append(ws)
                    else:
                        raise ValueError(f'No wire found for path {ps.ws_path}!')
                else:
                    wsegs.append(CONST_MAP_VAL2OBJ.get(ps.raw_ws_path, WIRE_SEGMENT_X))
        return P2V.simplify_wire_segments(curr_module, wsegs)

    def _get_unconnected_idx(self, port: ANY_PORT) -> List[int]:
        exclude_indices = [idx for idx, ps in port.segments.items() if ps.is_unconnected]
        if exclude_indices:
            LOG.warn(f'Excluding these segments from port {port.raw_path} from write-out, since they are unconnected: {exclude_indices}')
        return exclude_indices

    def _fix_signedness_mismatch(self, port_name: str, param_name: Literal['A_SIGNED', 'B_SIGNED']) -> bool:
        if getattr(self.parameters, param_name, False) != self.ports[port_name].signed:
            if hasattr(self.parameters, param_name) and 'signed' in self.ports[port_name].parameters:
                LOG.warn(
                    f"Detected parameter mismatch: Parameter {param_name} of instance {self.raw_path} is different from the port's parameter 'signed'. "
                    + 'To change the signedness of the port, change it directly at the port, via port.set_signed(new_value). '
                    + "Aligning param_name with the port's current parameter to fix the mismatch..."
                )
            self.ports[port_name].parameters['signed'] = getattr(self.parameters, param_name, False)
        return bool(getattr(self.parameters, param_name, False))

    def set(self, port_name: str, new_signal: SignalOrLogicLevel) -> None:
        """
        Sets the signal on a port.

        Args:
            port_name (str): The name of the port to set the signal on.
            new_signal (Signal): The new signal value.
        """
        self.ports[port_name].set_signal(new_signal)

    def evaluate(self) -> None:
        """
        Evaluates the gate's output signal based on its input signals.

        This method is called when the gate's input signals change, and it updates the gate's output signal accordingly.
        """
        new_signals = {}
        for i in range(self.data_width):
            new_signals.update(self._calc_output(i))
        self._set_output(new_signals=new_signals)

    def _calc_output(self, idx: NonNegativeInt = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal based on its input signals.

        This method is implemented by each specific gate class, and it returns the gate's output signal.
        """
        raise NotImplementedError(f'Not implemented for objects of type {type(self)}')

    def _set_output(self, new_signals: Dict[int, Signal]) -> None:
        """
        Sets the gate's output signal.

        This method is called when the gate's output signal needs to be updated, and it sets the gate's output signal to the specified value.

        Args:
            new_signals (Dict[int, Signal]): A dictionary mapping the new output signal values to the indices of the output port.
        """
        for idx, sig in new_signals.items():
            self.output_port.set_signal(signal=sig, index=idx)

    def _split(self) -> Dict[NonNegativeInt, Self]:
        new_insts: Dict[NonNegativeInt, Self] = {}
        connections = self.connections
        super_module = self.parent
        super_module.remove_instance(self.name)
        for idx in range(self.data_width):
            inst: Self = super_module.add_instance(self.__class__(name=f'{self.name}_{idx}'))
            for pname in list(inst.ports.keys()):
                p = inst.ports[pname]
                super_module.connect(connections[pname][idx], p[0])
            new_insts[idx] = inst
        return new_insts

    def _split_sync_params(self, slices: Iterable[Self]) -> None:
        super()._split_sync_params(slices)
        for inst in slices:
            inst.parameters.Y_WIDTH = 1


class UnaryGate(PrimitiveGate, BaseModel):
    """
    A base class for unary gates.

    Unary gates are gates that have a single input signal, and they produce a single output signal.
    This class provides a common interface for all unary gates, including methods for evaluating the gate's output and setting its output signal.
    """

    parameters: UnaryParams = UnaryParams()

    def model_post_init(self, __context: Optional[Dict[str, object]]) -> None:
        """
        Initializes the gate's ports and connections.

        This method is called after the gate's attributes have been initialized, and it sets up the gate's ports and connections.
        """
        self.connect('A', None, direction=Direction.IN, width=self.a_width)
        self.connect('Y', None, direction=Direction.OUT, width=self.y_width)
        return super().model_post_init(__context)

    @property
    def input_port(self) -> Port[Instance]:
        """The input port of the gate."""
        return self.ports['A']

    @property
    def y_width(self) -> PositiveInt:
        """Width of the gate, based on a certain port's width, depending on the actual gate."""
        self._try_sync_parameters()
        return self.parameters.Y_WIDTH or 1

    @property
    def a_width(self) -> PositiveInt:
        """Width of the gate's `A` port."""
        self._try_sync_parameters()
        return self.parameters.A_WIDTH or self.y_width

    @property
    def a_signed(self) -> bool:
        """The signedness of input port A."""
        return self._fix_signedness_mismatch('A', 'A_SIGNED')

    @property
    def output_port(self) -> Port[Instance]:
        """The output port of the gate."""
        return self.ports['Y']

    @property
    def splittable(self) -> bool:
        return True

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1};'

    @property
    def verilog_net_map(self) -> Dict[str, str]:
        exclude_indices = self._get_unconnected_idx(self.ports['Y'])
        out_str = self.p2v(self.ports['Y'], exclude_indices)
        in1_str = self.p2v(self.ports['A'], exclude_indices)
        return {'Y': out_str, 'A': in1_str}

    def _check_signal_signed(self, a: str) -> str:
        if self.a_signed:
            a = f'$signed({a})'
        return a

    @property
    def verilog(self) -> str:
        if any(self.ports['Y'][i].is_connected for i in self.ports['Y'].segments):
            return self.verilog_template.format(out=self.verilog_net_map['Y'], in1=self._check_signal_signed(self.verilog_net_map['A']))
        return ''

    def sync_parameters(self, warn: bool = True) -> Optional[UnaryParams]:
        super().sync_parameters(warn)
        self.parameters.A_WIDTH = self.ports['A'].width
        self.parameters.A_SIGNED = self.ports['A'].signed
        self.parameters.Y_WIDTH = self.data_width
        return self.parameters

    def signal_in(self, idx: NonNegativeInt = 0) -> Signal:
        """
        The input signal of the gate.

        Returns:
            Signal: The input signal of the gate.
        """
        return self.input_port.signal_array[idx]

    def signal_out(self, idx: NonNegativeInt = 0) -> Signal:
        """
        The output signal of the gate.

        Returns:
            Signal: The output signal of the gate.
        """
        return self.output_port.signal_array[idx]


class _Out1BitMixin(PrimitiveGate):
    @property
    def output_port(self) -> Port[Instance]:
        """The output port of the gate."""
        self._check_width()
        return self.ports['Y']

    def _check_width(self) -> None:
        if 'Y' in self.ports and self.ports['Y'].width != 1:
            raise WidthMismatchError(f'Reduce gates must have an output port width of 1, but {self.raw_path} is {self.output_port.width} bit wide!')

    @property
    def y_width(self) -> PositiveInt:
        """Width of the gate, which is always 1 for gates that reduce N-bit inputs to 1 bit."""
        self._check_width()
        return 1


class ReduceGate(_Out1BitMixin, UnaryGate):
    """
    A base class for reduce gates.

    Reduce gates are gates that have an n-bit input signal, and they produce a 1-bit output signal by performing a given reducing operation.
    This class provides a common interface for all reduce gates, including methods for evaluating the gate's output and setting its output signal.
    """

    parameters: UnaryParams = UnaryParams()

    def model_post_init(self, __context: Optional[Dict[str, object]]) -> None:
        """
        Initializes the gate's ports and connections.

        This method is called after the gate's attributes have been initialized, and it sets up the gate's ports and connections.
        """
        self.connect('A', None, direction=Direction.IN, width=self.a_width)
        self.connect('Y', None, direction=Direction.OUT)

    @property
    def splittable(self) -> bool:
        return False

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {operator}{in1};'

    @property
    def verilog_net_map(self) -> Dict[str, str]:
        exclude_indices = self._get_unconnected_idx(self.ports['A'])
        in1_str = self.p2v(self.ports['A'], exclude_indices)
        out_str = self.p2v(self.ports['Y'])
        return {'Y': out_str, 'A': in1_str}

    @property
    def verilog(self) -> str:
        # Check whether output is connected (i.e. self.p2ws2v(self.ports["Y"]) != "1'bx"), do not transform outgoing segments without connection
        out = self.verilog_net_map['Y']
        in1 = self.verilog_net_map['A']
        return self.verilog_template.format(out=out, in1=in1) if out != "1'bx" else ''

    def signal_out(self) -> Signal:  # type: ignore[override]
        """The output signal of the gate."""
        return self.output_port.signal


class BinaryGate(PrimitiveGate, BaseModel):
    """
    A base class for binary gates.

    Binary gates are gates that have two input signals, and they produce a single output signal.
    This class provides a common interface for all binary gates, including methods for evaluating the gate's output and setting its output signal.
    """

    parameters: BinaryParams = BinaryParams()

    def model_post_init(self, __context: Optional[Dict[str, object]]) -> None:
        """
        Initializes the gate's ports and connections.

        This method is called after the gate's attributes have been initialized, and it sets up the gate's ports and connections.
        """
        self.connect('A', None, direction=Direction.IN, width=self.a_width)
        self.connect('B', None, direction=Direction.IN, width=self.b_width)
        self.connect('Y', None, direction=Direction.OUT, width=self.y_width)
        return super().model_post_init(__context)

    @property
    def input_ports(self) -> Tuple[Port[Instance], Port[Instance]]:
        """The input ports of the gate as a 2-tuple."""
        return (self.ports['A'], self.ports['B'])

    @property
    def y_width(self) -> PositiveInt:
        """Width of the gate, based on a certain port's width, depending on the actual gate."""
        self._try_sync_parameters()
        return self.parameters.Y_WIDTH or 1

    @property
    def a_width(self) -> PositiveInt:
        """Width of the gate's `A` port."""
        self._try_sync_parameters()
        return self.parameters.A_WIDTH or self.y_width

    @property
    def a_signed(self) -> bool:
        """The signedness of input port A."""
        return self._fix_signedness_mismatch('A', 'A_SIGNED')

    @property
    def b_width(self) -> PositiveInt:
        """Width of the gate's `B` port."""
        self._try_sync_parameters()
        return self.parameters.B_WIDTH or self.y_width

    @property
    def b_signed(self) -> bool:
        """The signedness of input port B."""
        return self._fix_signedness_mismatch('B', 'B_SIGNED')

    @property
    def output_port(self) -> Port[Instance]:
        """The output port of the gate."""
        return self.ports['Y']

    @property
    def splittable(self) -> bool:
        return True

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1} {operator} {in2};'

    @property
    def verilog_net_map(self) -> Dict[str, str]:
        exclude_indices = self._get_unconnected_idx(self.ports['Y'])
        out_str = self.p2v(self.ports['Y'], exclude_indices)
        in1_str = self.p2v(self.ports['A'], exclude_indices)
        in2_str = self.p2v(self.ports['B'], exclude_indices)
        return {'Y': out_str, 'A': in1_str, 'B': in2_str}

    @property
    def verilog(self) -> str:
        if any(self.ports['Y'][i].is_connected for i in self.ports['Y'].segments):
            out = self.verilog_net_map['Y']
            in1, in2 = self._check_signal_signed(self.verilog_net_map['A'], self.verilog_net_map['B'])
            return self.verilog_template.format(out=out, in1=in1, in2=in2)
        return ''

    def sync_parameters(self, warn: bool = True) -> Optional[BinaryParams]:
        super().sync_parameters(warn)
        self.parameters.A_WIDTH = self.ports['A'].width
        self.parameters.A_SIGNED = self.ports['A'].signed
        self.parameters.B_WIDTH = self.ports['B'].width
        self.parameters.B_SIGNED = self.ports['B'].signed
        self.parameters.Y_WIDTH = self.data_width
        return self.parameters

    def _check_signal_signed(self, a: str, b: str) -> Tuple[str, str]:
        if self.a_signed:
            a = f'$signed({a})'
        if self.b_signed:
            b = f'$signed({b})'
        return (a, b)

    def signals_in(self, idx: NonNegativeInt = 0) -> Tuple[Signal, Signal]:
        """
        The input signals of the gate.

        Returns:
            Tuple[Signal, Signal]: The input signals of the gate.
        """
        return (self.input_ports[0].signal_array[idx], self.input_ports[1].signal_array[idx])

    def signal_out(self, idx: NonNegativeInt = 0) -> Signal:
        """
        The output signal of the gate.

        Returns:
            Signal: The output signal of the gate.
        """
        return self.output_port.signal_array[idx]


class ShiftGate(BinaryGate, BaseModel):
    @property
    def splittable(self) -> bool:
        return False

    def _check_signal_signed(self, a: str, b: str) -> Tuple[str, str]:
        if self.a_signed:
            a = f'$signed({a})'
        # Do not modify b to $signed({b}), because second operator of shift gates cannot be signed.
        return a, b


class ArithmeticGate(BinaryGate, BaseModel):
    """
    A base class for arithmetic gates.

    Arithmetic gates are gates that have two input signals representing numeric values, and they produce a single output signal.
    This class provides a common interface for all arithmetic gates, including methods for evaluating the gate's output and setting its output signal.
    """

    parameters: BinaryParams = BinaryParams()

    @property
    def input_ports(self) -> Tuple[Port[Instance], Port[Instance]]:
        """
        The input ports of the gate.

        Returns:
            Tuple[Port, Port]: The input ports of the gate.
        """
        return (self.ports['A'], self.ports['B'])

    @property
    def output_port(self) -> Port[Instance]:
        """
        The output port of the gate.

        Returns:
            Port: The output port of the gate.
        """
        return self.ports['Y']

    @property
    def splittable(self) -> bool:
        return False

    def _check_signal_signed(self, a: str, b: str) -> Tuple[str, str]:
        if self.a_signed:
            a = f'$signed({a})'
        if self.b_signed:
            b = f'$signed({b})'
        return (a, b)

    def evaluate(self) -> None:
        """
        Evaluates the gate's output signal based on its input signals.

        This method is called when the gate's input signals change, and it updates the gate's output signal accordingly.
        """
        new_signal_array = self._calc_output()
        self._set_output(new_signals=new_signal_array)

    def _unused_idx(self) -> List[int]:
        unused_bits = []
        if any(self.ports['Y'][i].is_unconnected for i in self.ports['Y'].segments):
            prev = list(self.ports['Y'].segments.values())[-1]
            for s in reversed(self.ports['Y'].segments.values()):  # Top bit first
                if s.is_unconnected:
                    unused_bits.append(s.index)
                    if prev.is_connected:
                        raise ValueError(
                            f'Cannot transform gate {self.raw_path} ({self.instance_type}) to Verilog: at least one bit of output {self.ports["Y"].raw_path} is Z!'
                        )
                prev = s
        return unused_bits

    @property
    def verilog_net_map(self) -> Dict[str, str]:
        unused_bits = self._unused_idx()
        out_str = self.p2v(self.output_port, unused_bits)
        in1_str = self.p2v(self.input_ports[0], unused_bits)
        in2_str = self.p2v(self.input_ports[1], unused_bits)
        return {'Y': out_str, 'A': in1_str, 'B': in2_str}

    @property
    def verilog(self) -> str:
        out = self.verilog_net_map['Y']
        in1, in2 = self._check_signal_signed(self.verilog_net_map['A'], self.verilog_net_map['B'])
        return self.verilog_template.format(out=out, in1=in1, in2=in2)

    def sync_parameters(self, warn: bool = True) -> Optional[BinaryParams]:
        super().sync_parameters(warn)
        self.parameters.A_WIDTH = self.ports['A'].width
        self.parameters.A_SIGNED = self.ports['A'].signed
        self.parameters.B_WIDTH = self.ports['B'].width
        self.parameters.B_SIGNED = self.ports['B'].signed
        self.parameters.Y_WIDTH = self.data_width
        return self.parameters

    def inputs_int(self) -> Tuple[int, int]:
        if self.input_ports[0].has_undefined_signals or self.input_ports[1].has_undefined_signals:
            err = f'Cannot calculate output signal for {self.__class__.__name__} {self.raw_path}: one of the inputs contain undefined signal values!'
            raise EvaluationError(err)
        sig1_int = Signal.dict_to_int(self.input_ports[0].signal_array, signed=self.a_signed)
        sig2_int = Signal.dict_to_int(self.input_ports[1].signal_array, signed=self.b_signed)
        return sig1_int, sig2_int


class BinaryNto1Gate(_Out1BitMixin, BinaryGate, BaseModel):
    parameters: BinaryParams = BinaryParams()

    def model_post_init(self, __context: Optional[Dict[str, object]]) -> None:
        """
        Initializes the gate's ports and connections.

        This method is called after the gate's attributes have been initialized, and it sets up the gate's ports and connections.
        """
        super().model_post_init(__context)
        self.connect('A', None, direction=Direction.IN, width=self.a_width)
        self.connect('B', None, direction=Direction.IN, width=self.b_width)
        self.connect('Y', None, direction=Direction.OUT)

    @property
    def splittable(self) -> bool:
        return False

    @property
    def verilog_net_map(self) -> Dict[str, str]:
        in1_str = self.p2v(self.ports['A'])
        in2_str = self.p2v(self.ports['B'])
        out_str = self.p2v(self.output_port)
        return {'Y': out_str, 'A': in1_str, 'B': in2_str}

    @property
    def verilog(self) -> str:
        out = self.verilog_net_map['Y']
        in1, in2 = self._check_signal_signed(self.verilog_net_map['A'], self.verilog_net_map['B'])
        # Check whether output is connected, do not transform if output port is unconnected
        return self.verilog_template.format(out=out, in1=in1, in2=in2) if out != "1'bx" else ''

    def evaluate(self) -> None:
        new_signal = self._calc_output()
        self._set_output(new_signals=new_signal)


class StorageGate(PrimitiveGate, BaseModel):
    parameters: DFFParams = DFFParams()

    def model_post_init(self, __context: Optional[Dict[str, object]]) -> None:
        """
        Initializes the gate's ports and connections.

        This method is called after the gate's attributes have been initialized, and it sets up the gate's ports and connections.
        """
        self.connect('D', None, direction=Direction.IN, width=self.width)
        self.connect('Q', None, direction=Direction.OUT, width=self.width)

        self._curr_out = [Signal.UNDEFINED for i in range(self.data_width)]
        return super().model_post_init(__context)

    @property
    def y_width(self) -> PositiveInt:
        warnings.warn(
            f'{self.__class__.__name__}.y_width is deprecated and will be removed in v1.0.0. Use {self.__class__.__name__}.width instead!',
            DeprecationWarning,
            stacklevel=2,
        )
        return self.width

    @property
    def width(self) -> PositiveInt:
        return self.parameters.WIDTH or 1

    @property
    def is_combinational(self) -> bool:
        return False

    @property
    def input_port(self) -> Port[Instance]:
        """The input port of the gate."""
        return self.ports['D']

    @property
    def output_port(self) -> Port[Instance]:
        """The output port of the gate."""
        return self.ports['Q']

    @property
    def splittable(self) -> bool:
        return True

    @property
    def verilog_context_map(self) -> SafeFormatDict:
        return SafeFormatDict()

    @property
    def verilog_net_map(self) -> Dict[str, str]:
        in1 = self.p2v(self.input_port)
        out = self.p2v(self.output_port)
        return {'Q': out, 'D': in1}

    def _storage_assigns(self, sig_value: str = '') -> str:
        out = self.verilog_net_map['Q']
        in1 = sig_value if sig_value != '' else self.verilog_net_map['D']
        return f'{out}\t<=\t{in1};' if out != "1'bx" else ''

    def _v_header(self, port: Port[Instance], polarity: Signal) -> str:
        wire = self.p2v(port) if self.p2v(port) != "1'bx" else ''
        return ('posedge ' if polarity == Signal.HIGH else 'negedge ') + wire if wire else ''

    def sync_parameters(self, warn: bool = True) -> Optional[Parameters]:
        super().sync_parameters(warn)
        self.parameters.WIDTH = self.data_width
        return self.parameters

    def _split(self) -> Dict[NonNegativeInt, Self]:
        new_insts: Dict[NonNegativeInt, Self] = {}
        connections = self.connections
        super_module = self.parent
        super_module.remove_instance(self.name)
        for idx in range(self.data_width):
            inst: Self = super_module.add_instance(self.__class__(name=f'{self.name}_{idx}'))
            for pname in list(inst.ports.keys()):
                p = inst.ports[pname]
                if pname == 'D' or pname == 'Q':
                    super_module.connect(connections[pname][idx], p[0])
                else:
                    for conn_idx in connections[pname]:
                        super_module.connect(connections[pname][conn_idx], p[conn_idx])

            new_insts[idx] = inst
        return new_insts

    def _split_sync_params(self, slices: Iterable[Self]) -> None:
        super()._split_sync_params(slices)
        for inst in slices:
            inst.parameters.WIDTH = 1


def _new_class_name_map() -> Dict[str, type]:
    from netlist_carpentry.utils.gate_mixins import ClkMixin, EnMixin, RstMixin, ScanMixin

    return {
        'EnMixin': EnMixin,
        'ClkMixin': ClkMixin,
        'RstMixin': RstMixin,
        'ScanMixin': ScanMixin,
    }


def __getattr__(name: str) -> object:
    if name in _new_class_name_map():
        new = _new_class_name_map()[name]
        warnings.warn(
            f"The '{name}' class is deprecated and will be removed in v1.0.0. Use '{new.__name__}' instead.",
            DeprecationWarning,
            stacklevel=2,  # Ensures the warning points to the user's code, not this line
        )
        return new
    # Standard behavior for missing attributes
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
