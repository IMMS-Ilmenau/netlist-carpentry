"""
The gate_lib module provides a library of digital gates and other netlist elements.

These gates are the basic building blocks of digital circuits, and they can be combined to create more complex circuits.
The module includes classes for various types of gates, including unary gates (such as buffers and inverters),
binary gates (such as AND, OR, and XOR gates), and more complex gates like multiplexers and demultiplexers.

Every primitive gate from this library has an `instance_type` string, which starts with an {CFG.nc_identifier_internal} (section symbol),
which is not a valid Verilog symbol for use in identifiers (except if escaped).
This is intended to distinguish primitive gates from user-defined module instances.
"""

import inspect
import sys
from typing import Dict, List, Optional, Tuple, Type, Union

from pydantic import BaseModel, PositiveInt

from netlist_carpentry import CFG
from netlist_carpentry.core.exceptions import EvaluationError
from netlist_carpentry.core.netlist_elements.port import Port
from netlist_carpentry.core.netlist_elements.port_segment import PortSegment
from netlist_carpentry.core.port_direction import PortDirection
from netlist_carpentry.core.protocols.netlist_elements import InstanceLike
from netlist_carpentry.core.signal import Signal
from netlist_carpentry.utils._gate_lib_base import (
    LibUtils,
    _ArithmeticGate,
    _BinaryGate,
    _BinaryNto1Gate,
    _ClockedGate,
    _PrimitiveGate,
    _ReduceGate,
    _ShiftGate,
    _StorageGate,
    _UnaryGate,
)

_gate_lib_map: Dict[str, Type[_PrimitiveGate]] = {}
"""
A dictionary mapping instance types to their corresponding primitive gate classes.

This map is used to look up the class of a primitive gate based on its instance type.
It provides an efficient way to access the different types of gates in the library.
"""


class Buffer(_UnaryGate, BaseModel):
    """
    A buffer gate.

    A buffer gate is a gate that simply passes its input signal to its output.
    It is used to isolate a signal or to drive a long wire.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
    """

    instance_type: str = f'{CFG.id_internal}buf'

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = {in1};'

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For a buffer gate, the output signal is simply the input signal.
        """
        return {idx: self.signal_in(idx) if self.signal_in(idx).is_defined else Signal.UNDEFINED}


class NotGate(_UnaryGate, BaseModel):
    """
    An inverter gate.

    An inverter gate is a gate that inverts its input signal.
    It produces a HIGH output signal if its input signal is LOW, and vice versa.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
    """

    instance_type: str = f'{CFG.id_internal}not'

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = ~{in1};'

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For an inverter gate, the output signal is the inverse of the input signal.
        """
        if self.signal_in(idx).is_defined:
            return {idx: Signal.HIGH if self.signal_in(idx) is Signal.LOW else Signal.LOW}
        return {idx: Signal.UNDEFINED}


class NegGate(_UnaryGate, BaseModel):
    """
    An arithmetic negator gate.

    An arithmetic negator gate is a gate that returns the two's complement of its input signal.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
    """

    instance_type: str = f'{CFG.id_internal}neg'

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = -{in1};'

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For an arithmetic negator gate, the output signal is the two's complement of the input signal.
        """
        if all(self.signal_in(i).is_defined for i in self.input_port.segments):
            signed = self.parameters['A_SIGNED'] == 1 if 'A_SIGNED' in self.parameters else False
            int_val = Signal.dict_to_int(self.input_port.signal_array, msb_first=self.input_port.msb_first, signed=signed)
            comp_str = Signal.twos_complement(int_val, width=self.output_port.width, msb_first=self.output_port.msb_first)
            return Signal.from_bin(comp_str, msb_first=self.output_port.msb_first, fixed_width=self.output_port.width)
        return {idx: Signal.UNDEFINED}


class ReduceAnd(_ReduceGate, BaseModel):
    """
    A reduction AND gate.

    A reduction AND gate performs a logical AND operation on all input signals.
    It produces a HIGH output signal if and only if all input signals are HIGH.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
    """

    instance_type: str = f'{CFG.id_internal}reduce_and'

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = &{in1};'

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For a reduction AND gate, the output signal is HIGH if and only if all input signals are HIGH.
        If any input signal is LOW or undefined, the output signal will be LOW or undefined, respectively.
        """
        if all(self.signal_in(i).is_defined for i in self.input_port.segments):
            return {idx: Signal.HIGH if all(self.signal_in(i) == Signal.HIGH for i in self.input_port.segments) else Signal.LOW}
        return {idx: Signal.UNDEFINED}


class ReduceOr(_ReduceGate, BaseModel):
    """
    A reduction OR gate.

    A reduction OR gate performs a logical OR operation on all input signals.
    It produces a HIGH output signal if at least one input signal is HIGH.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
    """

    instance_type: str = f'{CFG.id_internal}reduce_or'

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = |{in1};'

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For a reduction OR gate, the output signal is HIGH if at least one input signal is HIGH.
        If all input signals are LOW or undefined, the output signal will be LOW or undefined, respectively.
        """
        # In verilog corresponds to: '|wire_vector' (OR reduction)
        if any(self.signal_in(i) == Signal.HIGH for i in self.input_port.segments):
            return {idx: Signal.HIGH}
        return {idx: Signal.UNDEFINED if any(self.signal_in(i).is_undefined for i in self.input_port.segments) else Signal.LOW}


class ReduceBool(_ReduceGate, BaseModel):
    """
    A reduction Boolean gate.

    A reduction Boolean gate performs a logical OR operation on all input signals,
    but with the effect of a double negation (i.e., '!(!wire_vector)' in Verilog).
    It produces a HIGH output signal if at least one input signal is HIGH.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
    """

    instance_type: str = f'{CFG.id_internal}reduce_bool'

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = |{in1};'  # TODO EQY unable to prove equivalence for reduce bools sometimes...

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For a reduction Boolean gate, the output signal is HIGH if at least one input signal is HIGH.
        If all input signals are LOW or undefined, the output signal will be LOW or undefined, respectively.
        """
        # In verilog corresponds to: '!(!wire_vector)' (double negation, which has a similar effect like an OR reduction)
        if any(self.signal_in(i) == Signal.HIGH for i in self.input_port.segments):
            return {idx: Signal.HIGH}
        return {idx: Signal.UNDEFINED if any(self.signal_in(i).is_undefined for i in self.input_port.segments) else Signal.LOW}


class ReduceXor(_ReduceGate, BaseModel):
    """
    A reduction XOR gate.

    A reduction XOR gate performs a logical XOR operation on all input signals.
    It produces a HIGH output signal if an odd number of input signals are HIGH.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
    """

    instance_type: str = f'{CFG.id_internal}reduce_xor'

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = ^{in1};'

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For a reduction XOR gate, the output signal is HIGH if an odd number of input signals are HIGH.
        If an even number of input signals are HIGH or any input signal is undefined, the output signal will be LOW or undefined, respectively.
        """
        if all(self.signal_in(i).is_defined for i in self.input_port.segments):
            return {idx: Signal.HIGH if self.input_port.count_signals(Signal.HIGH) % 2 == 1 else Signal.LOW}
        return {idx: Signal.UNDEFINED}


class ReduceXnor(_ReduceGate, BaseModel):
    """
    A reduction XNOR gate.

    A reduction XNOR gate performs a logical XNOR operation on all input signals.
    It produces a HIGH output signal if an even number of input signals are HIGH.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
    """

    instance_type: str = f'{CFG.id_internal}reduce_xnor'

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = ~^{in1};'

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For a reduction XNOR gate, the output signal is HIGH if an even number of input signals are HIGH.
        If an odd number of input signals are HIGH or any input signal is undefined, the output signal will be LOW or undefined, respectively.
        """
        if all(self.signal_in(i).is_defined for i in self.input_port.segments):
            return {idx: Signal.HIGH if self.input_port.count_signals(Signal.HIGH) % 2 == 0 else Signal.LOW}
        return {idx: Signal.UNDEFINED}


class LogicNot(_ReduceGate, BaseModel):
    """
    A logic not gate.

    A logic not gate performs a logical not operation on all input signals.
    It produces a HIGH output signal if all input signals are LOW.
    The output is LOW, if any input signal is HIGH.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
    """

    instance_type: str = f'{CFG.id_internal}logic_not'

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = !{in1};'

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For a logic not gate, the output signal is HIGH if all input signals are LOW.
        The output is LOW, if any input signal is HIGH.
        """
        if all(self.signal_in(i).is_defined for i in self.input_port.segments):
            return {idx: Signal.LOW if any(self.signal_in(i) == Signal.HIGH for i in self.input_port.segments) else Signal.HIGH}
        return {idx: Signal.UNDEFINED}


class AndGate(_BinaryGate, BaseModel):
    """
    An AND gate.

    An AND gate is a gate that produces a HIGH output signal only if both its input signals are HIGH.
    Otherwise, it produces a LOW output signal.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
    """

    instance_type: str = f'{CFG.id_internal}and'

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = {in1} & {in2};'

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For an AND gate, the output signal is HIGH only if both input signals are HIGH.
        """
        if Signal.LOW in self.signals_in(idx):
            return {idx: Signal.LOW}
        if Signal.UNDEFINED in self.signals_in(idx) or Signal.FLOATING in self.signals_in(idx):
            return {idx: Signal.UNDEFINED}
        return {idx: Signal.HIGH}


class OrGate(_BinaryGate, BaseModel):
    """
    An OR gate.

    An OR gate is a gate that produces a HIGH output signal if either of its input signals is HIGH.
    Otherwise, it produces a LOW output signal.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
    """

    instance_type: str = f'{CFG.id_internal}or'

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = {in1} | {in2};'

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For an OR gate, the output signal is HIGH if either input signal is HIGH.
        """
        if Signal.HIGH in self.signals_in(idx):
            return {idx: Signal.HIGH}
        if Signal.UNDEFINED in self.signals_in(idx) or Signal.FLOATING in self.signals_in(idx):
            return {idx: Signal.UNDEFINED}
        return {idx: Signal.LOW}


class XorGate(_BinaryGate, BaseModel):
    """
    An XOR gate.

    An XOR gate is a gate that produces a HIGH output signal if its input signals are different.
    Otherwise, it produces a LOW output signal.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
    """

    instance_type: str = f'{CFG.id_internal}xor'

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = {in1} ^ {in2};'

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For an XOR gate, the output signal is HIGH if the input signals are different.
        """
        if Signal.UNDEFINED in self.signals_in(idx) or Signal.FLOATING in self.signals_in(idx):
            return {idx: Signal.UNDEFINED}
        return {idx: Signal.LOW if self.signals_in(idx)[0] is self.signals_in(idx)[1] else Signal.HIGH}


class XnorGate(_BinaryGate, BaseModel):
    """
    An XNOR gate.

    An XNOR gate is a gate that produces a HIGH output signal if its input signals are the same.
    Otherwise, it produces a LOW output signal.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
    """

    instance_type: str = f'{CFG.id_internal}xnor'

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = {in1} ^~ {in2};'

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For an XNOR gate, the output signal is HIGH if the input signals are the same.
        """
        if Signal.UNDEFINED in self.signals_in(idx) or Signal.FLOATING in self.signals_in(idx):
            return {idx: Signal.UNDEFINED}
        return {idx: Signal.HIGH if self.signals_in(idx)[0] is self.signals_in(idx)[1] else Signal.LOW}


class NorGate(_BinaryGate, BaseModel):
    """
    A NOR gate.

    A NOR gate is a gate that produces a LOW output signal if either of its input signals is HIGH.
    Otherwise, it produces a HIGH output signal.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
    """

    instance_type: str = f'{CFG.id_internal}nor'

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = ~({in1} | {in2});'

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For a NOR gate, the output signal is LOW if either input signal is HIGH.
        """
        if Signal.HIGH in self.signals_in(idx):
            return {idx: Signal.LOW}
        if Signal.UNDEFINED in self.signals_in(idx) or Signal.FLOATING in self.signals_in(idx):
            return {idx: Signal.UNDEFINED}
        return {idx: Signal.HIGH}


class NandGate(_BinaryGate, BaseModel):
    """
    A NAND gate.

    A NAND gate is a gate that produces a LOW output signal only if both its input signals are HIGH.
    Otherwise, it produces a HIGH output signal.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
    """

    instance_type: str = f'{CFG.id_internal}nand'

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = ~({in1} & {in2});'

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For a NAND gate, the output signal is LOW only if both input signals are HIGH.
        """
        if Signal.LOW in self.signals_in(idx):
            return {idx: Signal.HIGH}
        if Signal.UNDEFINED in self.signals_in(idx) or Signal.FLOATING in self.signals_in(idx):
            return {idx: Signal.UNDEFINED}
        return {idx: Signal.LOW}


class ShiftSigned(_ShiftGate, BaseModel):
    """
    A signed SHIFT gate.

    A signed SHIFT gate is a gate that returns its left input shifted right by the number on the right side
    if it is positive or unsigned, and shifted left by the number on the right side if it is negative.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
    """

    instance_type: str = f'{CFG.id_internal}shift'

    @property
    def verilog_template(self) -> str:
        shift_op = ' << -' if 'B_SIGNED' in self.parameters and int(self.parameters['B_SIGNED']) != 0 else ' >> '
        return 'assign {out} = {in1}' + shift_op + '{in2};'

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For a signed SHIFT gate, returns its left input shifted right by the number on the right side
        if it is positive or unsigned, and shifted left by the number on the right side if it is negative.
        """
        val_a = Signal.dict_to_int(self.ports['A'].signal_array, msb_first=self.ports['A'].msb_first, signed=self.ports['A'].signed)
        val_b = Signal.dict_to_int(self.ports['B'].signal_array, msb_first=self.ports['B'].msb_first, signed=self.ports['B'].signed)
        shift_left = self.ports['B'].signed and self.ports['B'].signal_int is not None and self.ports['B'].signal_int < 0
        out_val = val_a << -val_b if shift_left else val_a >> val_b
        return Signal.from_int(out_val, msb_first=self.ports['Y'].msb_first, fixed_width=self.ports['Y'].width)


class ShiftLeft(_ShiftGate, BaseModel):
    """
    A SHIFT-LEFT gate.

    A SHIFT-LEFT gate is a gate that returns its left input shifted left by the number on the right side.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
    """

    instance_type: str = f'{CFG.id_internal}shl'

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = {in1} << {in2};'

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For a SHIFT-LEFT gate, returns its left input shifted left by the number on the right side.
        """
        val_a = Signal.dict_to_int(self.ports['A'].signal_array, msb_first=self.ports['A'].msb_first)
        val_b = Signal.dict_to_int(self.ports['B'].signal_array, msb_first=self.ports['B'].msb_first)
        out_val = val_a << val_b
        return Signal.from_int(out_val, msb_first=self.ports['Y'].msb_first, fixed_width=self.ports['Y'].width)


class ShiftRight(_ShiftGate, BaseModel):
    """
    A SHIFT-RIGHT gate.

    A SHIFT-RIGHT gate is a gate that returns its left input shifted right by the number on the right side.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
    """

    instance_type: str = f'{CFG.id_internal}shr'

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = {in1} >> {in2};'

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For a SHIFT-RIGHT gate, returns its left input shifted right by the number on the right side.
        """
        val_a = Signal.dict_to_int(self.ports['A'].signal_array, msb_first=self.ports['A'].msb_first)
        val_b = Signal.dict_to_int(self.ports['B'].signal_array, msb_first=self.ports['B'].msb_first)
        out_val = val_a >> val_b
        return Signal.from_int(out_val, msb_first=self.ports['Y'].msb_first, fixed_width=self.ports['Y'].width)


class LogicAnd(_BinaryNto1Gate, BaseModel):
    """
    A LOGIC-AND gate.

    A LOGIC-AND gate is a gate that produces a HIGH output signal if both input signals are non-zero.
    Otherwise, it produces a LOW output signal.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
    """

    instance_type: str = f'{CFG.id_internal}logic_and'

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = {in1} && {in2};'

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For a LOGIC-AND gate, the output signal is HIGH if both input signals are non-zero.
        """
        sin1 = self.input_ports[0].signal_array
        sin2 = self.input_ports[1].signal_array
        if all(s.is_defined for s in sin1.values()) and all(s.is_defined for s in sin2.values()):
            # Both int(sin1) > 0 and int(sin2) > 0
            return {idx: Signal.HIGH if Signal.dict_to_int(sin1) and Signal.dict_to_int(sin2) else Signal.LOW}
        return {idx: Signal.UNDEFINED}


class LogicOr(_BinaryNto1Gate, BaseModel):
    """
    A LOGIC-OR gate.

    A LOGIC-OR gate is a gate that produces a HIGH output signal if at least one of both input signals is non-zero.
    Otherwise, it produces a LOW output signal.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
    """

    instance_type: str = f'{CFG.id_internal}logic_or'

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = {in1} || {in2};'

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For a LOGIC-OR gate, the output signal is HIGH if at least one of both input signals is non-zero.
        """
        sin1 = self.input_ports[0].signal_array
        sin2 = self.input_ports[1].signal_array
        if all(s.is_defined for s in sin1.values()) and all(s.is_defined for s in sin2.values()):
            # Either int(sin1) > 0 or int(sin2) > 0
            return {idx: Signal.HIGH if Signal.dict_to_int(sin1) or Signal.dict_to_int(sin2) else Signal.LOW}
        return {idx: Signal.UNDEFINED}


class LessThan(_BinaryNto1Gate, BaseModel):
    """
    A LESS-THAN gate.

    A LESS-THAN gate is a gate that produces a HIGH output signal only if its "left" input signal value is less than its "right" input signal.
    Otherwise, it produces a LOW output signal.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
    """

    instance_type: str = f'{CFG.id_internal}lt'

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = {in1} < {in2};'

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For a LESS-THAN gate, the output signal is HIGH only if its "left" input signal value is less than its "right" input signal.
        """
        sin1 = self.input_ports[0].signal_array
        sin2 = self.input_ports[1].signal_array
        if all(s.is_defined for s in sin1.values()) and all(s.is_defined for s in sin2.values()):
            return {idx: Signal.HIGH if Signal.dict_to_int(sin1) < Signal.dict_to_int(sin2) else Signal.LOW}
        return {idx: Signal.UNDEFINED}


class LessEqual(_BinaryNto1Gate, BaseModel):
    """
    A LESS-OR-EQUAL gate.

    A LESS-OR-EQUAL gate is a gate that produces a HIGH output signal if its "left" input signal value is less or equal to its "right" input signal.
    Otherwise, it produces a LOW output signal.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
    """

    instance_type: str = f'{CFG.id_internal}le'

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = {in1} <= {in2};'

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For a LESS-OR-EQUAL gate, the output signal is HIGH if its "left" input signal value is less or equal to its "right" input signal.
        """
        sin1 = self.input_ports[0].signal_array
        sin2 = self.input_ports[1].signal_array
        if all(s.is_defined for s in sin1.values()) and all(s.is_defined for s in sin2.values()):
            return {idx: Signal.HIGH if Signal.dict_to_int(sin1) <= Signal.dict_to_int(sin2) else Signal.LOW}
        return {idx: Signal.UNDEFINED}


class Equal(_BinaryNto1Gate, BaseModel):
    """
    An EQUAL gate.

    An EQUAL gate is a gate that produces a HIGH output signal only if both input signals have the same value.
    Otherwise, it produces a LOW output signal.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
    """

    instance_type: str = f'{CFG.id_internal}eq'

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = {in1} == {in2};'

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For an EQUAL gate, the output signal is HIGH only if both input signals have the same value.
        """
        sin1 = self.input_ports[0].signal_array
        sin2 = self.input_ports[1].signal_array
        if all(s.is_defined for s in sin1.values()) and all(s.is_defined for s in sin2.values()):
            return {idx: Signal.HIGH if Signal.dict_to_int(sin1) == Signal.dict_to_int(sin2) else Signal.LOW}
        return {idx: Signal.UNDEFINED}


class NotEqual(_BinaryNto1Gate, BaseModel):
    """
    A NOT-EQUAL gate.

    A NOT-EQUAL gate is a gate that produces a HIGH output signal only if both input signals have different values.
    Otherwise (if both are equal), it produces a LOW output signal.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
    """

    instance_type: str = f'{CFG.id_internal}ne'

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = {in1} != {in2};'

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For a NOT-EQUAL gate, the output signal is HIGH only if both input signals have different values.
        """
        sin1 = self.input_ports[0].signal_array
        sin2 = self.input_ports[1].signal_array
        if all(s.is_defined for s in sin1.values()) and all(s.is_defined for s in sin2.values()):
            return {idx: Signal.HIGH if Signal.dict_to_int(sin1) != Signal.dict_to_int(sin2) else Signal.LOW}
        return {idx: Signal.UNDEFINED}


class GreaterThan(_BinaryNto1Gate, BaseModel):
    """
    A GREATER-THAN gate.

    A GREATER-THAN gate is a gate that produces a HIGH output signal only if its "left" input signal value is greater than its "right" input signal.
    Otherwise, it produces a LOW output signal.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
    """

    instance_type: str = f'{CFG.id_internal}gt'

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = {in1} > {in2};'

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For a GREATER-THAN gate, the output signal is HIGH only if its "left" input signal value is greater than its "right" input signal.
        """
        sin1 = self.input_ports[0].signal_array
        sin2 = self.input_ports[1].signal_array
        if all(s.is_defined for s in sin1.values()) and all(s.is_defined for s in sin2.values()):
            return {idx: Signal.HIGH if Signal.dict_to_int(sin1) > Signal.dict_to_int(sin2) else Signal.LOW}
        return {idx: Signal.UNDEFINED}


class GreaterEqual(_BinaryNto1Gate, BaseModel):
    """
    A GREATER-OR-EQUAL gate.

    A GREATER-OR-EQUAL gate is a gate that produces a HIGH output signal if its "left" input signal value is greater or equal to its "right" input signal.
    Otherwise, it produces a LOW output signal.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
    """

    instance_type: str = f'{CFG.id_internal}ge'

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = {in1} >= {in2};'

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For a GREATER-OR-EQUAL gate, the output signal is HIGH if its "left" input signal value is greater or equal to its "right" input signal.
        """
        sin1 = self.input_ports[0].signal_array
        sin2 = self.input_ports[1].signal_array
        if all(s.is_defined for s in sin1.values()) and all(s.is_defined for s in sin2.values()):
            return {idx: Signal.HIGH if Signal.dict_to_int(sin1) >= Signal.dict_to_int(sin2) else Signal.LOW}
        return {idx: Signal.UNDEFINED}


class Multiplexer(_PrimitiveGate, BaseModel):
    """
    A multiplexer.

    A multiplexer is a gate that selects one of its input signals to be its output signal, based on a control signal.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
        bit_width (PositiveInt): The width of the control signal.
    """

    instance_type: str = f'{CFG.id_internal}mux'
    bit_width: PositiveInt = 1
    """
    The width of the multiplexer's control signal.

    Not to be confused with the data width of the multiplexer! The bit width indicates the width of the control signal,
    which is used to switch between all input paths. The total number of input paths is "2 to the power of bit_width".

    If bit_width is set to 1, there are 2^bitwidth = 2¹ = 2 input paths.
    If bit_width is set to 2, there are 2² = 4 input paths. ...
    """

    def model_post_init(self, __context: Optional[Dict[str, object]]) -> None:
        """
        Initializes the gate's ports and connections.

        This method is called after the gate's attributes have been initialized, and it sets up the gate's ports and connections.
        """
        for i in range(2**self.bit_width):
            self.connect(f'D_{i}', None, direction=PortDirection.IN, width=self.width)
        self.connect('S', None, direction=PortDirection.IN, width=self.bit_width)
        self.connect('Y', None, direction=PortDirection.OUT, width=self.width)
        return super().model_post_init(__context)

    @property
    def output_port(self) -> Port:
        """
        The output port of the multiplexer.

        Returns:
            Port: The output port of the multiplexer.
        """
        return self.ports['Y']

    @property
    def d_ports(self) -> List[Port]:
        """
        The data ports of the multiplexer.

        Returns:
            List[Port]: The data ports of the multiplexer.
        """
        return list(filter(self.is_d_port, self.ports.values()))

    @property
    def s_port(self) -> Port:
        """
        The select port of the multiplexer.

        Returns:
            Port: The select port of the multiplexer.
        """
        return self.ports['S']

    @property
    def s_defined(self) -> bool:
        """
        Whether the select signals are defined.

        Returns:
            bool: True if the select signals are defined, False otherwise.
        """
        return all(s.signal.is_defined for s in self.s_port.segments.values())

    @property
    def s_val(self) -> int:
        """
        The value of the select signals.

        Returns:
            int: The value of the select signals, or -1 if the select signals are not defined.
        """
        if self.s_defined:
            # Adding the binary values of all S_.. ports, whose value is HIGH
            # Example: S_2 == 1, S_1 == 1, and S_1 == 0
            # This is equal to: 1*2^2 + 1*2^1 + 0*2^0 == 4+2 == 6,
            # which is the binary representation of the select signals. Thus, s_val == 6!
            return sum(2 ** int(s.index) if (s.signal is Signal.HIGH) else 0 for s in self.s_port.segments.values())
        return -1

    @property
    def active_input(self) -> Optional[Port]:
        """
        The active input port of the gate.

        Returns:
            Port: The active input port of the gate, or None if the select signals are not defined.
        """
        if self.s_defined:
            return self.ports[f'D_{self.s_val}']
        return None

    @property
    def verilog_template(self) -> str:
        return 'always @(*) begin\n\tcase ({sel})\n{cases}\n\tendcase\nend'

    @property
    def verilog(self) -> str:
        """
        Creates a Verilog multiplexer from the Python object.

        This method generates the Verilog code for the multiplexer gate.
        It uses the `verilog_template` property as a base and fills in the
        select signal and cases.

        The cases are generated by iterating over all possible values of the
        select signal (i.e., from 0 to 2^bit_width - 1) and creating a case
        for each value. In each case, the output signals are assigned the value
        of the input signal if the current case matches the select signal.

        Returns:
            str: The Verilog code for the multiplexer gate.
        """
        cases = ''
        exclude_indices = LibUtils.get_unconnected_idx(self.output_port)
        if self.bit_width > 1:
            for i in range(2**self.bit_width):
                d_port = self.ports[f'D_{i}']
                out_signals = LibUtils.p2ws2v(self.output_port, exclude_indices)
                in_signals = LibUtils.p2ws2v(d_port, exclude_indices)
                cases += f"\t\t{self.bit_width}'b{format(i, f'0{self.bit_width}b')} : {out_signals} <= {in_signals};\n"
            return self.verilog_template.format(sel=LibUtils.p2ws2v(self.ports['S']), cases=cases[:-1])
        return self._verilog_ternary_form

    @property
    def _verilog_ternary_form(self) -> str:
        """
        Creates a Verilog string in ternary form for the multiplexer gate.

        The ternary form follows the format:
        assign `out_signal` = `condition` ? `value_if_true` : `value_if_false`;

        Returns:
            str: The Verilog code for the multiplexer gate in ternary form.
        """
        exclude_indices = LibUtils.get_unconnected_idx(self.output_port)
        out_signals = LibUtils.p2ws2v(self.output_port, exclude_indices)
        sel = LibUtils.p2ws2v(self.s_port)
        val_false = LibUtils.p2ws2v(self.ports['D_0'], exclude_indices)
        val_true = LibUtils.p2ws2v(self.ports['D_1'], exclude_indices)
        return f'assign\t{out_signals}\t= {sel} ? {val_true} : {val_false};'

    def is_d_port(self, port: Port) -> bool:
        """
        Whether a port is a data port.

        Args:
            port (Port): The port to check.

        Returns:
            bool: True if the port is a data port, False otherwise.
        """
        return 'D_' in port.name and port.is_input

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For a multiplexer, the output signal is the signal from the selected input port.
        """
        return {idx: self.active_input.signal_array[idx] if self.active_input.signal_array[idx].is_defined else Signal.UNDEFINED}


class Demultiplexer(_PrimitiveGate, BaseModel):
    """
    A demultiplexer.

    A demultiplexer is a gate that selects one of its output ports to be connected to its input signal, based on a control signal.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
        bit_width (PositiveInt): The width of the control signal.
    """

    instance_type: str = f'{CFG.id_internal}demux'
    bit_width: PositiveInt = 1
    """
    The width of the demultiplexer's control signal.

    Not to be confused with the data width of the demultiplexer! The bit width indicates the width of the control signal,
    which is used to switch between all output paths. The total number of output paths is "2 to the power of bit_width".

    If bit_width is set to 1, there are 2^bitwidth = 2¹ = 2 output paths.
    If bit_width is set to 2, there are 2² = 4 output paths. ...
    """
    inactive_out_value: Signal = Signal.UNDEFINED

    def model_post_init(self, __context: Optional[Dict[str, object]]) -> None:
        """
        Initializes the gate's ports and connections.

        This method is called after the gate's attributes have been initialized, and it sets up the gate's ports and connections.
        """
        self.connect('D', None, direction=PortDirection.IN, width=self.width)
        self.connect('S', None, direction=PortDirection.IN, width=self.bit_width)
        for i in range(2**self.bit_width):
            self.connect(f'Y_{i}', None, direction=PortDirection.OUT, width=self.width)
        return super().model_post_init(__context)

    @property
    def input_port(self) -> Port:
        """
        The input port of the gate.

        Returns:
            Port: The input port of the gate.
        """
        return self.ports['D']

    @property
    def y_ports(self) -> List[Port]:
        """
        The output ports of the gate.

        Returns:
            List[Port]: The output ports of the gate.
        """
        return list(filter(self.is_y_port, self.ports.values()))

    @property
    def s_port(self) -> Port:
        """
        The select ports of the gate.

        Returns:
            List[Port]: The select ports of the gate.
        """
        return self.ports['S']

    @property
    def s_defined(self) -> bool:
        """
        Whether the select signals are defined.

        Returns:
            bool: True if the select signals are defined, False otherwise.
        """
        return all(s.signal.is_defined for s in self.s_port.segments.values())

    @property
    def s_val(self) -> int:
        """
        Initializes the gate's ports and connections.

        This method is called after the gate's attributes have been initialized, and it sets up the gate's ports and connections.
        """
        if self.s_defined:
            # Adding the binary values of all S_.. ports, whose value is HIGH
            # Example: S_2 == 1, S_1 == 1, and S_1 == 0
            # This is equal to: 1*2^2 + 1*2^1 + 0*2^0 == 4+2 == 6,
            # which is the binary representation of the select signals. Thus, s_val == 6!
            return sum(2 ** int(s.index) if (s.signal is Signal.HIGH) else 0 for s in self.s_port.segments.values())
        return -1

    @property
    def active_output(self) -> Optional[Port]:
        """
        The active output port of the gate.

        Returns:
            Port: The active output port of the gate, or None if the select signals are not defined.
        """
        if self.s_defined:
            return self.ports[f'Y_{self.s_val}']
        return None

    @property
    def data_width(self) -> int:
        return self.input_port.width

    @property
    def verilog_template(self) -> str:
        return 'always @(*) begin\n\tcase ({sel})\n{cases}\n\tendcase\nend'

    @property
    def verilog(self) -> str:
        """
        Creates a Verilog demultiplexer from the Python object.

        This method generates the Verilog code for the demultiplexer gate.
        It uses the `verilog_template` property as a base and fills in the
        select signal and cases.

        The cases are generated by iterating over all possible values of the
        select signal (i.e., from 0 to 2^bit_width - 1) and creating a case
        for each value. In each case, the output signals are assigned the value
        of the input signal if the current case matches the select signal.

        Returns:
            str: The Verilog code for the demultiplexer gate.
        """
        cases = ''
        for i in range(2**self.bit_width):
            y_port = self.ports[f'Y_{i}']
            exclude_indices = LibUtils.get_unconnected_idx(y_port)
            out_signals = LibUtils.p2ws2v(y_port, exclude_indices)
            in_signals = LibUtils.p2ws2v(self.input_port, exclude_indices)
            cases += f"\t\t{self.bit_width}'b{format(i, f'0{self.bit_width}b')} : {out_signals} <= {in_signals};\n"
        return self.verilog_template.format(sel=LibUtils.p2ws2v(self.ports['S']), cases=cases[:-1])

    def is_y_port(self, port: Port) -> bool:
        """
        Whether a port is an output port.

        Args:
            port (Port): The port to check.

        Returns:
            bool: True if the port is an output port, False otherwise.
        """
        return 'Y_' in port.name and port.is_output

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For a demultiplexer, the output signal is the input signal.
        """
        return {idx: self.input_port.signal_array[idx]}

    def _set_output(self, new_signals: Dict[int, Signal]) -> None:
        """
        Sets the gate's output signal.

        For a demultiplexer, the output signal is set on the active output port.

        Args:
            new_signals (Dict[int, Signal]): A dictionary mapping the new output signal values to the indices of the output port.
        """
        # Set all undriven outputs to "z": only change the signal on the only active output path
        for y in self.y_ports:
            for idx in y.segments:
                y.set_signal(self.inactive_out_value, index=idx)
        if self.active_output is not None:
            for idx, sig in new_signals.items():
                self.active_output.set_signal(sig if sig.is_defined else Signal.UNDEFINED, index=idx)


class Adder(_ArithmeticGate, BaseModel):
    instance_type: str = f'{CFG.id_internal}add'

    @property
    def input_ports(self) -> Tuple[Port, Port]:
        """
        The input ports of the gate.

        Returns:
            Tuple[Port, Port]: The input ports of the gate.
        """
        return (self.ports['A'], self.ports['B'])

    @property
    def output_port(self) -> Port:
        """
        The output port of the gate.

        Returns:
            Port: The output port of the gate.
        """
        return self.ports['Y']

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = {in1} + {in2};'

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For an ADD gate, the output signal is the sum of both input signals.
        """
        if self.input_ports[0].has_undefined_signals or self.input_ports[1].has_undefined_signals:
            err = f'Cannot calculate output signal for {self.__class__.__name__} {self.raw_path}: one of the inputs contain undefined signal values!'
            raise EvaluationError(err)
        signed_a = self.parameters['A_SIGNED'] == 1 if 'A_SIGNED' in self.parameters else False
        signed_b = self.parameters['B_SIGNED'] == 1 if 'B_SIGNED' in self.parameters else False
        sig1_int = Signal.dict_to_int(self.input_ports[0].signal_array, signed=signed_a)
        sig2_int = Signal.dict_to_int(self.input_ports[1].signal_array, signed=signed_b)

        sig_sum = Signal.from_int(sig1_int + sig2_int, fixed_width=self.output_port.width)
        return sig_sum


class Subtractor(_ArithmeticGate, BaseModel):
    instance_type: str = f'{CFG.id_internal}sub'

    @property
    def input_ports(self) -> Tuple[Port, Port]:
        """
        The input ports of the gate.

        Returns:
            Tuple[Port, Port]: The input ports of the gate.
        """
        return (self.ports['A'], self.ports['B'])

    @property
    def output_port(self) -> Port:
        """
        The output port of the gate.

        Returns:
            Port: The output port of the gate.
        """
        return self.ports['Y']

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = {in1} - {in2};'

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For an SUB gate, the output signal is the first input signal minus the second input signal.
        """
        if self.input_ports[0].has_undefined_signals or self.input_ports[1].has_undefined_signals:
            err = f'Cannot calculate output signal for {self.__class__.__name__} {self.raw_path}: one of the inputs contain undefined signal values!'
            raise EvaluationError(err)
        signed_a = self.parameters['A_SIGNED'] == 1 if 'A_SIGNED' in self.parameters else False
        signed_b = self.parameters['B_SIGNED'] == 1 if 'B_SIGNED' in self.parameters else False
        sig1_int = Signal.dict_to_int(self.input_ports[0].signal_array, signed=signed_a)
        sig2_int = Signal.dict_to_int(self.input_ports[1].signal_array, signed=signed_b)

        sig_sum = Signal.from_int(sig1_int - sig2_int, fixed_width=self.output_port.width)
        return sig_sum


class Multiplier(_ArithmeticGate, BaseModel):
    instance_type: str = f'{CFG.id_internal}mul'

    @property
    def input_ports(self) -> Tuple[Port, Port]:
        """
        The input ports of the gate.

        Returns:
            Tuple[Port, Port]: The input ports of the gate.
        """
        return (self.ports['A'], self.ports['B'])

    @property
    def output_port(self) -> Port:
        """
        The output port of the gate.

        Returns:
            Port: The output port of the gate.
        """
        return self.ports['Y']

    @property
    def verilog_template(self) -> str:
        return 'assign {out} = {in1} * {in2};'

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For a MUL gate, the output signal is the product of both input signals.
        """
        if self.input_ports[0].has_undefined_signals or self.input_ports[1].has_undefined_signals:
            err = f'Cannot calculate output signal for {self.__class__.__name__} {self.raw_path}: one of the inputs contain undefined signal values!'
            raise EvaluationError(err)
        signed_a = self.parameters['A_SIGNED'] == 1 if 'A_SIGNED' in self.parameters else False
        signed_b = self.parameters['B_SIGNED'] == 1 if 'B_SIGNED' in self.parameters else False
        sig1_int = Signal.dict_to_int(self.input_ports[0].signal_array, signed=signed_a)
        sig2_int = Signal.dict_to_int(self.input_ports[1].signal_array, signed=signed_b)

        sig_sum = Signal.from_int(sig1_int * sig2_int, fixed_width=self.output_port.width)
        return sig_sum


class DFF(_ClockedGate, BaseModel):
    """A D flip-flop.
    A D flip-flop is a clocked gate that stores a value on its input port and outputs it on its output port.
    The value is stored when the clock signal has a rising edge.

    Attributes:
        name (str): The name of the gate instance.
        instance_type (str): The type of the gate.
        en_polarity (Signal): The polarity of the enable signal.
    """

    instance_type: str = f'{CFG.id_internal}dff'
    """
    Instance type descriptor for D-Flip-Flops. Defaults to §dff, but may be overwritten upon creation by Yosys.

    Yosys introduces a variety of flip-flop descriptor types. See the Yosys documentation for more information.
    """
    en_polarity: Signal = Signal.HIGH
    """Which EN-signal level enables the flip-flop. Default is Signal.HIGH."""

    @property
    def init_finished(self) -> bool:
        """
        Whether the gate has been initialized.

        Returns:
            bool: True if the gate has been initialized, False otherwise.
        """
        return self._init_finished

    @property
    def in_reset(self) -> bool:
        """
        Whether the gate is in reset.

        Returns:
            bool: True if the gate is in reset, False otherwise.
        """
        return self.rst_port.signal is self.rst_polarity

    @property
    def reset_ended_just_now(self) -> bool:
        """
        Whether the reset signal has just ended.

        Returns:
            bool: True if the reset signal has just ended, False otherwise.
        """
        return (self.rst_polarity is Signal.HIGH and self.rst_fedge) or (self.rst_polarity is Signal.LOW and self.rst_redge)

    @property
    def activated_just_now(self) -> bool:
        """
        Whether the gate has been activated.

        Returns:
            bool: True if the gate has been activated, False otherwise.
        """
        return (self.clk_polarity is Signal.HIGH and self.clk_redge) or (self.clk_polarity is Signal.LOW and self.clk_fedge)

    @property
    def verilog_template(self) -> str:
        if self.rst_port[0].is_unconnected:
            return 'always @({clk}{two_sig}{rst}) begin\n\t{set_out}\nend'
        return 'always @({clk}{two_sig}{rst}) begin\n\tif ({is_rst}) begin\n\t\t{rst_out}\n\tend else{enable}begin\n\t\t{set_out}\n\tend\nend'

    def _ff_assigns(self, sig_value: str = '') -> str:
        in1 = sig_value if sig_value != '' else LibUtils.p2ws2v(self.input_port)
        out = LibUtils.p2ws2v(self.output_port)
        return f'{out}\t<=\t{in1};' if out != "1'bx" else ''

    @property
    def verilog(self) -> str:
        # Collect wires
        clk_wire = LibUtils.p2ws2v(self.clk_port) if LibUtils.p2ws2v(self.clk_port) != "1'bx" else ''
        rst_wire = LibUtils.p2ws2v(self.rst_port) if LibUtils.p2ws2v(self.rst_port) != "1'bx" else ''
        en_wire = LibUtils.p2ws2v(self.en_port) if LibUtils.p2ws2v(self.en_port) != "1'bx" else ''
        # Build always block header structure
        clk = ('posedge ' if self.clk_polarity == Signal.HIGH else 'negedge ') + clk_wire if clk_wire else ''
        rst = ('posedge ' if self.rst_polarity == Signal.HIGH else 'negedge ') + rst_wire if rst_wire else ''
        two_sig = ' or ' if clk and rst else ''
        # When to reset
        is_rst = rst_wire if self.rst_polarity == Signal.HIGH else f'~{rst_wire}'
        # Build enable structure (if available)
        inv = '' if self.en_polarity == Signal.HIGH else '~'
        enable = ' if ({inv}{en}) '.format(inv=inv, en=en_wire) if en_wire else ' '

        # Build what happens inside the reset and set clauses
        rst_sig_val = f"{self.output_port.width}'b{f'{Signal.dict_to_bin(self.rst_val)}'.zfill(self.output_port.width)}"
        rst_out = self._ff_assigns(sig_value=rst_sig_val)
        set_out = self._ff_assigns()
        return self.verilog_template.format(clk=clk, two_sig=two_sig, rst=rst, is_rst=is_rst, rst_out=rst_out, set_out=set_out, enable=enable)

    def set(self, port: Port, new_signal: Signal) -> bool:
        """
        Sets the signal on a port.

        Args:
            port (Port): The port to set the signal on.
            new_signal (Signal): The new signal value.
        """
        return port.set_signal(new_signal)

    def set_clk(self, new_signal: Signal) -> bool:
        """
        Sets the clock signal.

        Args:
            new_signal (Signal): The new clock signal value.
        """
        return self.set(self.clk_port, new_signal)

    def set_rst(self, new_signal: Signal) -> bool:
        """
        Sets the reset signal.

        Args:
            new_signal (Signal): The new reset signal value.
        """
        return self.set(self.rst_port, new_signal)

    def set_en(self, new_signal: Signal) -> bool:
        """
        Sets the enable signal.

        Args:
            new_signal (Signal): The new enable signal value.
        """
        return self.set(self.en_port, new_signal)

    def _edge_detection(self, curr_val: Signal, new_val: Signal) -> Tuple[Signal, bool, bool]:
        """
        Detects the rising and falling edges of a signal.

        Args:
            curr_val (Signal): The current signal value.
            new_val (Signal): The new signal value.

        Returns:
            Tuple[Signal, bool, bool]: A tuple containing the updated current signal value and the states of the rising and falling edges.
        """
        if curr_val is not new_val:
            redge, fedge = False, False
            # Detect CLK edge
            prev_val = curr_val
            curr_val = new_val
            if prev_val is Signal.LOW and new_val is Signal.HIGH:
                # Found rising edge
                redge = True
            elif prev_val is Signal.HIGH and new_val is Signal.LOW:
                # Found falling edge
                fedge = True
            return (prev_val, redge, fedge)
        return (curr_val, False, False)

    def _is_segment_of(self, port_name: str, e: Union[Port, PortSegment]) -> bool:
        return isinstance(e, PortSegment) and e.parent_name == port_name

    def _reset_edges(self) -> None:
        self._clk_redge = False
        self._clk_fedge = False
        self._rst_redge = False
        self._rst_fedge = False

    def on_notification(self, element: Union[Port, PortSegment]) -> bool:
        """
        Handles notifications from other elements.

        Args:
            element: The element that sent the notification.
        """
        anything_done = False
        if self._is_segment_of('CLK', element):
            self._reset_edges()
            anything_done = element.signal is not self._curr_clk
            self._prev_clk, self._clk_redge, self._clk_fedge = self._edge_detection(self._curr_clk, element.signal)
            self._curr_clk = element.signal
        if self._is_segment_of('RST', element):
            self._reset_edges()
            anything_done = element.signal is not self._curr_rst
            self._prev_rst, self._rst_redge, self._rst_fedge = self._edge_detection(self._curr_rst, element.signal)
            self._curr_rst = element.signal
            if not self.init_finished and self.reset_ended_just_now:
                self._init_finished = True
        self.evaluate()
        return anything_done

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        """
        Calculates the gate's output signal.

        For a D flip-flop, the output signal is the input signal when the clock signal has a rising edge and the enable signal is high.
        Otherwise, the output signal is the previous output signal.

        Args:
            idx (int, optional): The idx of the output signal. Defaults to 0.

        Returns:
            Signal: The output signal value.
        """
        if self.in_reset or self.reset_ended_just_now:
            self._curr_out[idx] = self.rst_val[idx]
            return {idx: self._curr_out[idx]}
        if self.activated_just_now:
            if self.en_polarity.is_defined and self.en_signal is self.en_polarity:
                self._curr_out[idx] = self.input_port[idx].signal
        return {idx: self._curr_out[idx] if self._curr_out[idx].is_defined else Signal.UNDEFINED}

    def evaluate(self) -> None:
        """
        Evaluates the gate's output signal.

        This method is called when the gate's input signals change, and it updates the gate's output signal accordingly.
        """
        if len(self._curr_out) < self.data_width:
            self._curr_out += [Signal.UNDEFINED] * (self.data_width - len(self._curr_out))
        for i in range(self.data_width):
            new_signals = self._calc_output(idx=i)
            self._set_output(new_signals=new_signals)


class DLatch(_StorageGate, BaseModel):
    instance_type: str = f'{CFG.id_internal}dlatch'
    en_polarity: Signal = Signal.HIGH
    """Which EN-signal level makes the latch transparent. Default is Signal.HIGH.
    """

    def model_post_init(self, __context: Optional[Dict[str, object]]) -> None:
        """
        Initializes the gate's ports and connections.

        This method is called after the gate's attributes have been initialized, and it sets up the gate's ports and connections.
        """
        self._init_finished = False

        return super().model_post_init(__context)

    @property
    def init_finished(self) -> bool:
        return self._init_finished

    @property
    def verilog_template(self) -> str:
        return 'always @(*) begin\n\tif ({en}) begin\n{assignments}\n\tend\nend'

    @property
    def verilog(self) -> str:
        en = LibUtils.p2ws2v(self.en_port)
        en = f'~{en}' if self.en_polarity is Signal.LOW else en
        exclude_indices = LibUtils.get_unconnected_idx(self.output_port)
        assignments = f'\t\t{LibUtils.p2ws2v(self.output_port, exclude_indices)} = {LibUtils.p2ws2v(self.input_port, exclude_indices)};'
        return self.verilog_template.format(en=en, assignments=assignments)

    def evaluate(self) -> None:
        """
        Evaluates the gate's output signal.

        This method is called when the gate's input signals change, and it updates the gate's output signal accordingly.
        """
        for i in range(self.data_width):
            new_signals = self._calc_output(idx=i)
            self._set_output(new_signals=new_signals)

    def _calc_output(self, idx: int = 0) -> Dict[int, Signal]:
        if self.en_signal == self.en_polarity:
            return {idx: self.input_port.signal_array[idx]}
        return {idx: self.output_port.signal_array[idx]}


def get(instance_type: str) -> Union[type[_PrimitiveGate], None]:
    """
    Retrieves the class of a primitive gate based on its instance type.

    This function is needed to find the correct class for a primitive gate
    given its instance type. It searches for a class in the gate_lib module,
    whose instance type matches the given `instance_type` string.

    Args:
        instance_type (str): The instance type of the primitive gate.

    Returns:
        Union[type[_PrimitiveGate], None]: The class of the primitive gate or None if not found.
    """
    if not _gate_lib_map:
        _build_gate_lib_map()
    return _gate_lib_map[instance_type] if instance_type in _gate_lib_map else None


def _build_gate_lib_map() -> None:
    clsmembers: List[Tuple[str, type]] = inspect.getmembers(sys.modules[__name__], inspect.isclass)
    for _, c in clsmembers:
        # Iterate through all class members (i.e. all gates),
        # filter out all classes not being gates
        try:
            # Only works if a class extends _Primitive gate and will raise an exception otherwise
            c_inst: InstanceLike = c(raw_path='', module=None)

            # Add the found class to the gate_lib_map
            _gate_lib_map[c_inst.instance_type] = c
        except Exception:  # noqa: PERF203 YES, catching exceptions inside a loop might be bad, I just DONT CARE
            pass
