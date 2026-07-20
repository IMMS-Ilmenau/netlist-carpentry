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
from typing import Callable, Dict, List, Optional, Tuple, Type, Union

from pydantic import BaseModel, NonNegativeInt
from typing_extensions import Self

from netlist_carpentry import CFG, Direction, Instance, Module, Signal, SignalArray
from netlist_carpentry.core.protocols.signals import SignalOrLogicLevel
from netlist_carpentry.utils.gate_lib_base_classes import (
    ArithmeticGate,
    BinaryGate,
    BinaryNto1Gate,
    NtoOneGate,
    OneToNGate,
    PrimitiveGate,
    ReduceGate,
    ShiftGate,
    StorageGate,
    UnaryGate,
)
from netlist_carpentry.utils.gate_lib_dataclasses import DFFParams, DLatchParams
from netlist_carpentry.utils.gate_mixins import ClkMixin, EnMixin, LoadMixin, RstMixin, ScanMixin, SRMixin
from netlist_carpentry.utils.safe_format_dict import SafeFormatDict

_gate_lib_map: Dict[str, Type[PrimitiveGate]] = {}
"""
A dictionary mapping instance types to their corresponding primitive gate classes.

This map is used to look up the class of a primitive gate based on its instance type.
It provides an efficient way to access the different types of gates in the library.
"""


class Buffer(UnaryGate, BaseModel):
    """
    A buffer gate.

    A buffer gate is a gate that simply passes its input signal to its output.
    It is used to isolate a signal or to drive a long wire.
    """

    instance_type: str = f'{CFG.id_internal}buf'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1};'

    def get_result(self, s: Signal) -> Signal:
        return s if s.is_defined else Signal.UNDEFINED


class NotGate(UnaryGate, BaseModel):
    """
    An inverter gate.

    An inverter gate is a gate that inverts its input signal.
    It produces a HIGH output signal if its input signal is LOW, and vice versa.
    """

    instance_type: str = f'{CFG.id_internal}not'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = ~{in1};'

    def get_result(self, s: Signal) -> Signal:
        return ~s


class PosGate(UnaryGate, BaseModel):
    """
    An arithmetic plus gate.

    An arithmetic plus gate is a gate that just returns its input signal, sign extended.
    """

    instance_type: str = f'{CFG.id_internal}pos'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = +{in1};'

    def get_result_vector(self, s: SignalArray) -> SignalArray:
        if s.is_defined:
            int_val = int(s) or 0
            return SignalArray.from_int(int_val, msb_first=self.output_port.msb_first, fixed_width=self.output_port.width)
        return SignalArray(signals={idx: Signal.UNDEFINED for idx in range(self.output_port.width)})


class NegGate(UnaryGate, BaseModel):
    """
    An arithmetic negator gate.

    An arithmetic negator gate is a gate that returns the two's complement of its input signal.
    """

    instance_type: str = f'{CFG.id_internal}neg'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = -{in1};'

    def get_result_vector(self, s: SignalArray) -> SignalArray:
        if s.is_defined:
            int_val = int(s) or 0
            comp_str = Signal.twos_complement(int_val, width=self.output_port.width, msb_first=self.output_port.msb_first)
            return SignalArray.from_bin(comp_str, msb_first=self.output_port.msb_first, fixed_width=self.output_port.width)
        return SignalArray(signals={idx: Signal.UNDEFINED for idx in range(self.output_port.width)})


class ReduceAnd(ReduceGate, BaseModel):
    """
    A reduction AND gate.

    A reduction AND gate performs a logical AND operation on all input signals.
    It produces a HIGH output signal if and only if all input signals are HIGH.
    """

    instance_type: str = f'{CFG.id_internal}reduce_and'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = &{in1};'

    @property
    def reduce_operation(self) -> Callable[[Signal, Signal], Signal]:
        """Provides a lambda function for this gate.

        The lambda function takes two signals and executes this gate's operation on both of them.
        In junction with `functools.reduce()`, this reduces the input signal array down to a single
        bit by concatenating the operation of this gate bit-by-bit.

        For a reduction AND gate, the output signal is HIGH if and only if all input signals are HIGH.
        If any input signal is LOW or undefined, the output signal will be LOW or undefined, respectively.
        """
        return lambda s1, s2: s1 & s2


class ReduceOr(ReduceGate, BaseModel):
    """
    A reduction OR gate.

    A reduction OR gate performs a logical OR operation on all input signals.
    It produces a HIGH output signal if at least one input signal is HIGH.
    """

    instance_type: str = f'{CFG.id_internal}reduce_or'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = |{in1};'

    @property
    def reduce_operation(self) -> Callable[[Signal, Signal], Signal]:
        """Provides a lambda function for this gate.

        The lambda function takes two signals and executes this gate's operation on both of them.
        In junction with `functools.reduce()`, this reduces the input signal array down to a single
        bit by concatenating the operation of this gate bit-by-bit.

        For a reduction OR gate, the output signal is HIGH if at least one input signal is HIGH.
        If all input signals are LOW or undefined, the output signal will be LOW or undefined, respectively.
        """
        return lambda s1, s2: s1 | s2


class ReduceBool(ReduceGate, BaseModel):
    """
    A reduction Boolean gate.

    A reduction Boolean gate performs a logical OR operation on all input signals,
    but with the effect of a double negation (i.e., '!(!wire_vector)' in Verilog).
    It produces a HIGH output signal if at least one input signal is HIGH.
    """

    instance_type: str = f'{CFG.id_internal}reduce_bool'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = |{in1};'  # TODO EQY unable to prove equivalence for reduce bools sometimes...

    @property
    def reduce_operation(self) -> Callable[[Signal, Signal], Signal]:
        """Provides a lambda function for this gate.

        The lambda function takes two signals and executes this gate's operation on both of them.
        In junction with `functools.reduce()`, this reduces the input signal array down to a single
        bit by concatenating the operation of this gate bit-by-bit.

        For a reduction Boolean gate, the output signal is HIGH if at least one input signal is HIGH.
        If all input signals are LOW or undefined, the output signal will be LOW or undefined, respectively.
        """
        return lambda s1, s2: s1 | s2


class ReduceXor(ReduceGate, BaseModel):
    """
    A reduction XOR gate.

    A reduction XOR gate performs a logical XOR operation on all input signals.
    It produces a HIGH output signal if an odd number of input signals are HIGH.
    """

    instance_type: str = f'{CFG.id_internal}reduce_xor'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = ^{in1};'

    @property
    def reduce_operation(self) -> Callable[[Signal, Signal], Signal]:
        """Provides a lambda function for this gate.

        The lambda function takes two signals and executes this gate's operation on both of them.
        In junction with `functools.reduce()`, this reduces the input signal array down to a single
        bit by concatenating the operation of this gate bit-by-bit.

        For a reduction XOR gate, the output signal is HIGH if an odd number of input signals are HIGH.
        If an even number of input signals are HIGH or any input signal is undefined, the output signal will be LOW or undefined, respectively.
        """
        return lambda s1, s2: s1 ^ s2


class ReduceXnor(ReduceGate, BaseModel):
    """
    A reduction XNOR gate.

    A reduction XNOR gate performs a logical XNOR operation on all input signals.
    It produces a HIGH output signal if an even number of input signals are HIGH.
    """

    instance_type: str = f'{CFG.id_internal}reduce_xnor'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = ~^{in1};'

    @property
    def reduce_operation(self) -> Callable[[Signal, Signal], Signal]:
        """Provides a lambda function for this gate.

        The lambda function takes two signals and executes this gate's operation on both of them.
        In junction with `functools.reduce()`, this reduces the input signal array down to a single
        bit by concatenating the operation of this gate bit-by-bit.

        For a reduction XNOR gate, the output signal is HIGH if an even number of input signals are HIGH.
        If an odd number of input signals are HIGH or any input signal is undefined, the output signal will be LOW or undefined, respectively.
        """
        return lambda s1, s2: ~(s1 ^ s2)


class LogicNot(ReduceGate, BaseModel):
    """
    A logic not gate.

    A logic not gate performs a logical not operation on all input signals.
    It produces a HIGH output signal if all input signals are LOW.
    The output is LOW, if any input signal is HIGH.
    If there are undefined bits, the result is also UNDEFINED.
    """

    instance_type: str = f'{CFG.id_internal}logic_not'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = !{in1};'

    @property
    def reduce_operation(self) -> Callable[[Signal, Signal], Signal]:
        """**Returns the raw reduction, without the inversion**!

        Provides a lambda function for this gate.

        The lambda function takes two signals and executes this gate's operation on both of them.
        In junction with `functools.reduce()`, this reduces the input signal array down to a single
        bit by concatenating the operation of this gate bit-by-bit.

        For a logic not gate, the output signal is HIGH if all input signals are LOW.
        The output is LOW, if any input signal is HIGH.
        If there are undefined bits, the result is also UNDEFINED.
        """
        return lambda s1, s2: s1 | s2

    def get_result_vector(self, s: SignalArray) -> SignalArray:
        return ~super().get_result_vector(s)


class AndGate(BinaryGate, BaseModel):
    """
    An AND gate.

    An AND gate is a gate that produces a HIGH output signal only if both its input signals are HIGH.
    Otherwise, it produces a LOW output signal.
    """

    instance_type: str = f'{CFG.id_internal}and'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1} & {in2};'

    def get_result(self, s1: Signal, s2: Signal) -> Signal:
        return s1 & s2


class OrGate(BinaryGate, BaseModel):
    """
    An OR gate.

    An OR gate is a gate that produces a HIGH output signal if either of its input signals is HIGH.
    Otherwise, it produces a LOW output signal.
    """

    instance_type: str = f'{CFG.id_internal}or'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1} | {in2};'

    def get_result(self, s1: Signal, s2: Signal) -> Signal:
        return s1 | s2


class XorGate(BinaryGate, BaseModel):
    """
    An XOR gate.

    An XOR gate is a gate that produces a HIGH output signal if its input signals are different.
    Otherwise, it produces a LOW output signal.
    """

    instance_type: str = f'{CFG.id_internal}xor'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1} ^ {in2};'

    def get_result(self, s1: Signal, s2: Signal) -> Signal:
        return s1 ^ s2


class XnorGate(BinaryGate, BaseModel):
    """
    An XNOR gate.

    An XNOR gate is a gate that produces a HIGH output signal if its input signals are the same.
    Otherwise, it produces a LOW output signal.
    """

    instance_type: str = f'{CFG.id_internal}xnor'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1} ^~ {in2};'

    def get_result(self, s1: Signal, s2: Signal) -> Signal:
        return ~(s1 ^ s2)


class NorGate(BinaryGate, BaseModel):
    """
    A NOR gate.

    A NOR gate is a gate that produces a LOW output signal if either of its input signals is HIGH.
    Otherwise, it produces a HIGH output signal.
    """

    instance_type: str = f'{CFG.id_internal}nor'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = ~({in1} | {in2});'

    def get_result(self, s1: Signal, s2: Signal) -> Signal:
        return ~(s1 | s2)


class NandGate(BinaryGate, BaseModel):
    """
    A NAND gate.

    A NAND gate is a gate that produces a LOW output signal only if both its input signals are HIGH.
    Otherwise, it produces a HIGH output signal.
    """

    instance_type: str = f'{CFG.id_internal}nand'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = ~({in1} & {in2});'

    def get_result(self, s1: Signal, s2: Signal) -> Signal:
        return ~(s1 & s2)


class BitwiseCaseEquality(BinaryGate, BaseModel):
    """
    A BITWISE CASE EQUALITY gate.

    A BITWISE CASE EQUALITY gate is a gate that compares the input vectors bit by bit and
    produces a HIGH output signal for a certain bit only if both its input signals are HIGH.
    Otherwise, it produces a LOW output signal.
    """

    instance_type: str = f'{CFG.id_internal}bweqx'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1} === {in2};'

    def get_result(self, s1: Signal, s2: Signal) -> Signal:
        return Signal.HIGH if s1 is s2 else Signal.LOW


class ShiftSigned(ShiftGate, BaseModel):
    """
    A signed SHIFT gate.

    A signed SHIFT gate is a gate that returns its left input shifted right by the number on the right side
    if it is positive or unsigned, and shifted left by the number on the right side if it is negative.
    """

    instance_type: str = f'{CFG.id_internal}shift'

    @property
    def verilog_template(self) -> str:
        shift_op = ' << -' if self.b_signed else ' >> '
        return 'assign\t{out} = {in1}' + shift_op + '{in2};'

    def get_result_vector(self, s1: SignalArray, s2: SignalArray) -> SignalArray:
        if not s2.is_defined:
            return SignalArray(signals={idx: Signal.UNDEFINED for idx in range(self.data_width)})
        shift_left = self.b_signed and int(s2) is not None and int(s2) < 0
        out_val = s1 << -int(s2) if shift_left else s1 >> s2
        return out_val


class ShiftLeft(ShiftGate, BaseModel):
    """
    A SHIFT-LEFT gate.

    A SHIFT-LEFT gate is a gate that returns its left input shifted left by the number on the right side.
    """

    instance_type: str = f'{CFG.id_internal}shl'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1} << {in2};'

    def get_result_vector(self, s1: SignalArray, s2: SignalArray) -> SignalArray:
        if not s2.is_defined:
            return SignalArray(signals={idx: Signal.UNDEFINED for idx in range(self.data_width)})
        out_val = s1 << s2
        return out_val


class ShiftRight(ShiftGate, BaseModel):
    """
    A SHIFT-RIGHT gate.

    A SHIFT-RIGHT gate is a gate that returns its left input shifted right by the number on the right side.
    """

    instance_type: str = f'{CFG.id_internal}shr'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1} >> {in2};'

    def get_result_vector(self, s1: SignalArray, s2: SignalArray) -> SignalArray:
        if not s2.is_defined:
            return SignalArray(signals={idx: Signal.UNDEFINED for idx in range(self.data_width)})
        val_a = self.ports['A'].signal_array
        val_b = self.ports['B'].signal_array
        val_a.signed = False
        val_b.signed = False
        out_val = val_a >> val_b
        return out_val


class ArithmeticShiftLeft(ShiftGate, BaseModel):
    """
    An ARITHMETIC SHIFT-LEFT gate.

    An ARITHMETIC SHIFT-LEFT gate is a gate that returns its left input shifted left by the number on the right side.
    """

    instance_type: str = f'{CFG.id_internal}sshl'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1} <<< {in2};'

    def get_result_vector(self, s1: SignalArray, s2: SignalArray) -> SignalArray:
        if not s2.is_defined:
            return SignalArray(signals={idx: Signal.UNDEFINED for idx in range(self.data_width)})
        out_val = s1 << s2
        return out_val


class ArithmeticShiftRight(ShiftGate, BaseModel):
    """
    An ARITHMETIC SHIFT-RIGHT gate.

    An ARITHMETIC SHIFT-RIGHT gate is a gate that returns its left input shifted right by the number on the right side.
    """

    instance_type: str = f'{CFG.id_internal}sshr'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1} >>> {in2};'

    def get_result_vector(self, s1: SignalArray, s2: SignalArray) -> SignalArray:
        if not s2.is_defined:
            return SignalArray(signals={idx: Signal.UNDEFINED for idx in range(self.data_width)})
        out_val = s1 >> s2
        return out_val


class ShiftX(ShiftGate, BaseModel):
    """
    A SHIFT-X gate.

    A SHIFT-X gate is a gate that returns its first input shifted right or left by the number on the second input,
    based on whether the second input is signed and negative or not.
    """

    instance_type: str = f'{CFG.id_internal}shiftx'

    def model_post_init(self, __context: object) -> None:
        """
        Initializes the gate's ports and connections.

        This method is called after the gate's attributes have been initialized, and it sets up the gate's ports and connections.
        """
        a_width = self.parameters.A_WIDTH or 1
        b_width = self.parameters.B_WIDTH or 1
        y_width = self.parameters.Y_WIDTH or 1
        self.connect('A', None, direction=Direction.IN, width=a_width)
        self.connect('B', None, direction=Direction.IN, width=b_width)
        self.connect('Y', None, direction=Direction.OUT, width=y_width)

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1}[{in2} +: {width}];'

    @property
    def verilog_net_map(self) -> Dict[str, str]:
        out_str = self.p2v(self.ports['Y'])
        in1_str = self.p2v(self.ports['A'])
        in2_str = self.p2v(self.ports['B'])
        return {'Y': out_str, 'A': in1_str, 'B': in2_str}

    @property
    def verilog(self) -> str:
        if any(self.ports['Y'][i].is_connected for i in self.ports['Y'].segments):
            out = self.verilog_net_map['Y']
            in1, in2 = self._check_signal_signed(self.verilog_net_map['A'], self.verilog_net_map['B'])
            if not self.ports['A'].is_connected_1to1:
                wdt = self.ports['A'].width
                off = self.ports['A'].offset or 0
                i = 0
                while self.parent.name_occupied(f'{self.name}_A{i}'):
                    i += 1
                new_wire = f'wire [{wdt + off}:{off}] {f"{self.name}_A{i}"} = {self.verilog_net_map["A"]};\n'
                in1 = f'{self.name}_A{i}'
            else:
                new_wire = ''
            width = self.output_port.width
            return new_wire + self.verilog_template.format(out=out, in1=in1, in2=in2, width=width)
        return ''

    def _check_signal_signed(self, a: str, b: str) -> Tuple[str, str]:
        if self.a_signed:
            a = f'$signed({a})'
        if self.b_signed:
            b = f'$signed({b})'
        return (a, b)

    def _calc_output(self) -> SignalArray:
        return super()._calc_output()  # TODO implement for indexed part-select operator


class LogicAnd(BinaryNto1Gate, BaseModel):
    """
    A LOGIC-AND gate.

    A LOGIC-AND gate is a gate that produces a HIGH output signal if both input signals are non-zero.
    Otherwise, it produces a LOW output signal.
    """

    instance_type: str = f'{CFG.id_internal}logic_and'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1} && {in2};'

    def get_result_vector(self, s1: SignalArray, s2: SignalArray) -> SignalArray:
        if s1.is_defined and s2.is_defined:
            return SignalArray(signals={0: Signal.HIGH if int(s1) and int(s2) else Signal.LOW})
        return SignalArray(signals={0: Signal.UNDEFINED})


class LogicOr(BinaryNto1Gate, BaseModel):
    """
    A LOGIC-OR gate.

    A LOGIC-OR gate is a gate that produces a HIGH output signal if at least one of both input signals is non-zero.
    Otherwise, it produces a LOW output signal.
    """

    instance_type: str = f'{CFG.id_internal}logic_or'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1} || {in2};'

    def get_result_vector(self, s1: SignalArray, s2: SignalArray) -> SignalArray:
        if s1.is_defined and s2.is_defined:
            return SignalArray(signals={0: Signal.HIGH if int(s1) or int(s2) else Signal.LOW})
        return SignalArray(signals={0: Signal.UNDEFINED})


class LessThan(BinaryNto1Gate, BaseModel):
    """
    A LESS-THAN gate.

    A LESS-THAN gate is a gate that produces a HIGH output signal only if its "left" input signal value is less than its "right" input signal.
    Otherwise, it produces a LOW output signal.
    """

    instance_type: str = f'{CFG.id_internal}lt'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1} < {in2};'

    def get_result_vector(self, s1: SignalArray, s2: SignalArray) -> SignalArray:
        if s1.is_defined and s2.is_defined:
            return SignalArray(signals={0: Signal.HIGH if int(s1) < int(s2) else Signal.LOW})
        return SignalArray(signals={0: Signal.UNDEFINED})


class LessEqual(BinaryNto1Gate, BaseModel):
    """
    A LESS-OR-EQUAL gate.

    A LESS-OR-EQUAL gate is a gate that produces a HIGH output signal if its "left" input signal value is less or equal to its "right" input signal.
    Otherwise, it produces a LOW output signal.
    """

    instance_type: str = f'{CFG.id_internal}le'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1} <= {in2};'

    def get_result_vector(self, s1: SignalArray, s2: SignalArray) -> SignalArray:
        if s1.is_defined and s2.is_defined:
            return SignalArray(signals={0: Signal.HIGH if int(s1) <= int(s2) else Signal.LOW})
        return SignalArray(signals={0: Signal.UNDEFINED})


class Equal(BinaryNto1Gate, BaseModel):
    """
    An EQUAL gate.

    An EQUAL gate is a gate that produces a HIGH output signal only if both input signals have the same value.
    Otherwise, it produces a LOW output signal. Produces UNDEFINED, if one of the input signals is `x` or `z`.
    """

    instance_type: str = f'{CFG.id_internal}eq'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1} == {in2};'

    def get_result_vector(self, s1: SignalArray, s2: SignalArray) -> SignalArray:
        if s1.is_defined and s2.is_defined:
            return SignalArray(signals={0: Signal.HIGH if int(s1) == int(s2) else Signal.LOW})
        return SignalArray(signals={0: Signal.UNDEFINED})


class CaseEqual(BinaryNto1Gate, BaseModel):
    """
    A CASE-EQUAL gate.

    A CASE-EQUAL gate is a gate that produces a HIGH output signal only if both input signals have the same value.
    Otherwise, it produces a LOW output signal.

    Unlike the normal equality comparison (Equal gate, §eq) that can give `x` as output, this gate produces an exact equality comparison.
    It will strictly give `0` or `1` as output, even if input includes `x` or `z` values, implementing the Verilog `===` operator.
    """

    instance_type: str = f'{CFG.id_internal}eqx'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1} === {in2};'

    def get_result_vector(self, s1: SignalArray, s2: SignalArray) -> SignalArray:
        sigs_eq = s1 == s2
        sign_eq = s1.signed == s2.signed
        return SignalArray(signals={0: Signal.HIGH if sigs_eq and sign_eq else Signal.LOW})


class NotEqual(BinaryNto1Gate, BaseModel):
    """
    A NOT-EQUAL gate.

    A NOT-EQUAL gate is a gate that produces a HIGH output signal only if both input signals have different values.
    Otherwise (if both are equal), it produces a LOW output signal. Produces UNDEFINED, if one of the input signals is `x` or `z`.
    """

    instance_type: str = f'{CFG.id_internal}ne'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1} != {in2};'

    def get_result_vector(self, s1: SignalArray, s2: SignalArray) -> SignalArray:
        if s1.is_defined and s2.is_defined:
            return SignalArray(signals={0: Signal.HIGH if int(s1) != int(s2) else Signal.LOW})
        return SignalArray(signals={0: Signal.UNDEFINED})


class CaseNotEqual(BinaryNto1Gate, BaseModel):
    """
    A CASE-NOT-EQUAL gate.

    A CASE-NOT-EQUAL gate is a gate that produces a HIGH output signal only if both input signals have different values.
    Otherwise (if both are equal), it produces a LOW output signal.

    Unlike the normal inequality comparison (NotEqual gate, §ne) that can give `x` as output, this gate produces an exact inequality comparison.
    It will strictly give `0` or `1` as output, even if input includes `x` or `z` values, implementing the Verilog `!==` operator.
    """

    instance_type: str = f'{CFG.id_internal}nex'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1} !== {in2};'

    def get_result_vector(self, s1: SignalArray, s2: SignalArray) -> SignalArray:
        sigs_eq = s1 == s2
        sign_eq = s1.signed == s2.signed
        return SignalArray(signals={0: Signal.LOW if sigs_eq and sign_eq else Signal.HIGH})


class GreaterThan(BinaryNto1Gate, BaseModel):
    """
    A GREATER-THAN gate.

    A GREATER-THAN gate is a gate that produces a HIGH output signal only if its "left" input signal value is greater than its "right" input signal.
    Otherwise, it produces a LOW output signal.
    """

    instance_type: str = f'{CFG.id_internal}gt'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1} > {in2};'

    def get_result_vector(self, s1: SignalArray, s2: SignalArray) -> SignalArray:
        if s1.is_defined and s2.is_defined:
            return SignalArray(signals={0: Signal.HIGH if int(s1) > int(s2) else Signal.LOW})
        return SignalArray(signals={0: Signal.UNDEFINED})


class GreaterEqual(BinaryNto1Gate, BaseModel):
    """
    A GREATER-OR-EQUAL gate.

    A GREATER-OR-EQUAL gate is a gate that produces a HIGH output signal if its "left" input signal value is greater or equal to its "right" input signal.
    Otherwise, it produces a LOW output signal.
    """

    instance_type: str = f'{CFG.id_internal}ge'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1} >= {in2};'

    def get_result_vector(self, s1: SignalArray, s2: SignalArray) -> SignalArray:
        if s1.is_defined and s2.is_defined:
            return SignalArray(signals={0: Signal.HIGH if int(s1) >= int(s2) else Signal.LOW})
        return SignalArray(signals={0: Signal.UNDEFINED})


class Multiplexer(NtoOneGate):
    """
    A multiplexer.

    A multiplexer is a gate that selects one of its input signals to be its output signal, based on a control signal.
    """

    instance_type: str = f'{CFG.id_internal}mux'

    def _split(self) -> Dict[NonNegativeInt, Self]:
        new_insts: Dict[NonNegativeInt, Self] = {}
        connections = self.connections
        super_module = self.parent
        super_module.remove_instance(self.name)
        self.update_parameters()
        for idx in range(self.data_width):
            self.parameters.WIDTH = 1
            inst: Self = self.__class__(name=f'{self.name}_{idx}', parameters=self.parameters, module=super_module)
            for pname in list(inst.ports.keys()):
                p = inst.ports[pname]
                if pname != 'S':
                    super_module.connect(connections[pname][idx], p[0])
                else:
                    for conn_idx in connections[pname]:
                        super_module.connect(connections[pname][conn_idx], p[conn_idx])
            new_insts[idx] = inst
        return new_insts

    def get_result_vector(self, select: SignalArray, data: Dict[str, SignalArray]) -> SignalArray:
        if not select.is_defined:
            return SignalArray(signals={idx: Signal.UNDEFINED for idx in range(self.y_width)})
        sel_val = int(select)
        port_name = f'D{sel_val}'
        if port_name in data:
            # Convert undefined signals (including FLOATING) to UNDEFINED
            return SignalArray(signals={idx: sig if sig.is_defined else Signal.UNDEFINED for idx, sig in data[port_name].items()})
        return SignalArray(signals={idx: Signal.UNDEFINED for idx in range(self.y_width)})


class Demultiplexer(OneToNGate):
    """
    A demultiplexer.

    A demultiplexer is a gate that selects one of its output ports to be connected to its input signal, based on a control signal.
    """

    instance_type: str = f'{CFG.id_internal}demux'

    def _split(self) -> Dict[NonNegativeInt, Self]:
        new_insts: Dict[NonNegativeInt, Self] = {}
        connections = self.connections
        super_module = self.parent
        super_module.remove_instance(self.name)
        self.update_parameters()
        for idx in range(self.data_width):
            self.parameters.WIDTH = 1
            inst: Self = self.__class__(name=f'{self.name}_{idx}', parameters=self.parameters, module=super_module)
            for pname in list(inst.ports.keys()):
                p = inst.ports[pname]
                if pname != 'S':
                    super_module.connect(connections[pname][idx], p[0])
                else:
                    for conn_idx in connections[pname]:
                        super_module.connect(connections[pname][conn_idx], p[conn_idx])
            new_insts[idx] = inst
        return new_insts


class Adder(ArithmeticGate, BaseModel):
    instance_type: str = f'{CFG.id_internal}add'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1} + {in2};'

    def get_result_vector(self, s1: SignalArray, s2: SignalArray) -> SignalArray:
        sig1_int = int(s1)
        sig2_int = int(s2)
        return SignalArray.from_int(sig1_int + sig2_int, fixed_width=self.output_port.width, truncate=True)


class Subtractor(ArithmeticGate, BaseModel):
    instance_type: str = f'{CFG.id_internal}sub'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1} - {in2};'

    def get_result_vector(self, s1: SignalArray, s2: SignalArray) -> SignalArray:
        sig1_int = int(s1)
        sig2_int = int(s2)
        return SignalArray.from_int(sig1_int - sig2_int, fixed_width=self.output_port.width, truncate=True)


class Multiplier(ArithmeticGate, BaseModel):
    instance_type: str = f'{CFG.id_internal}mul'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1} * {in2};'

    def get_result_vector(self, s1: SignalArray, s2: SignalArray) -> SignalArray:
        sig1_int = int(s1)
        sig2_int = int(s2)
        return SignalArray.from_int(sig1_int * sig2_int, fixed_width=self.output_port.width, truncate=True)


class Divider(ArithmeticGate, BaseModel):
    instance_type: str = f'{CFG.id_internal}div'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1} / {in2};'

    def get_result_vector(self, s1: SignalArray, s2: SignalArray) -> SignalArray:
        sig1_int = int(s1)
        sig2_int = int(s2)
        return SignalArray.from_int(int(sig1_int / sig2_int), fixed_width=self.output_port.width, truncate=True)


class Modulo(ArithmeticGate, BaseModel):
    instance_type: str = f'{CFG.id_internal}mod'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1} % {in2};'

    def get_result_vector(self, s1: SignalArray, s2: SignalArray) -> SignalArray:
        sig1_int = int(s1)
        sig2_int = int(s2)
        return SignalArray.from_int(sig1_int % sig2_int, fixed_width=self.output_port.width, truncate=True)


class Exponentiator(ArithmeticGate, BaseModel):
    instance_type: str = f'{CFG.id_internal}pow'

    @property
    def verilog_template(self) -> str:
        return 'assign\t{out} = {in1} ** {in2};'

    def _verilog_pow(self) -> Optional[int]:
        base, expo = self.inputs_int()
        mask = (1 << self.y_width) - 1
        b_val = base & mask
        e_val = expo & mask
        if expo < 0:
            if base == 0:
                return None  # Division by Zero
            elif base == 1:  # 1**something is 1
                result = 1
            elif base == -1:  # -1**something is 1 or -1, alternating for odd and even
                result = -1 if (e_val % 2) else 1  # 1 for even e_val, -1 for odd e_val
            else:
                result = 0  # Truncation for fractions, truncate to 0
        else:  # Default case for positive e_val
            # pow calculates massive exponents efficiently and applies the hardware
            # wrap-around (modulo 2^N) automatically
            result = pow(b_val, e_val, 1 << self.y_width)

        self.output_port.set_signed(self.ports['A'].signed)
        if self.ports['A'].signed:  # Make the calculated number negative if it has a leading 1
            return result if result < (1 << self.y_width - 1) else result - (1 << self.y_width)
        return result

    def _calc_output(self) -> SignalArray:
        """
        Calculates the gate's output signal.

        For a POW gate, the output signal is the first input signal to the power of the second input signal.

        **Edge case:**
        0**0 is defined as 1, following IEEE 754-2008
        (https://en.wikipedia.org/wiki/Zero_to_the_power_of_zero#IEEE_floating-point_standard).
        """
        # Set signedness on output port before computing result
        self.output_port.set_signed(self.ports['A'].signed)
        return self.get_result_vector(self.input_ports[0].signal_array, self.input_ports[1].signal_array)

    def get_result_vector(self, s1: SignalArray, s2: SignalArray) -> SignalArray:
        base, expo = int(s1), int(s2)
        mask = (1 << self.output_port.width) - 1
        b_val = base & mask
        e_val = expo & mask
        if expo < 0:
            if base == 0:
                return SignalArray(signals={i: Signal.UNDEFINED for i in range(self.output_port.width)})
            elif base == 1:
                result = 1
            elif base == -1:
                result = -1 if (e_val % 2) else 1
            else:
                result = 0
        else:
            result = pow(b_val, e_val, 1 << self.output_port.width)
        return SignalArray.from_int(result, fixed_width=self.output_port.width, truncate=True)


class DFF(ClkMixin, StorageGate, BaseModel):
    """
    A D flip-flop (DFF) is a clocked gate that stores a value on its input port and outputs it on its output port.
    The value is stored when the clock signal has a rising edge.
    The most basic version only has 3 ports: D, Q and CLK.
        en_polarity (Signal): The polarity of the enable signal.
    """

    instance_type: str = f'{CFG.id_internal}dff'
    """
    Instance type descriptor for D-Flip-Flops. Defaults to §dff, but may be overwritten upon creation by Yosys.

    Yosys introduces a variety of flip-flop descriptor types. See the Yosys documentation for more information.
    """
    parameters: DFFParams = DFFParams()

    prev_signals: Dict[str, SignalArray] = {}

    @property
    def has_en(self) -> bool:
        """Whether this DFF instance has an EN (enable) port."""
        return 'EN' in self.ports

    @property
    def has_rst(self) -> bool:
        """Whether this DFF instance has an RST (reset) port."""
        return 'RST' in self.ports

    @property
    def scan_ff_equivalent(self) -> Type['ScanDFF']:
        """Returns the Scan-FF type equivalent for normal FF and the FF type equivalent for Scan-FF."""
        mapping: Dict[str, Type['ScanDFF']] = {
            '§dff': ScanDFF,
            '§adff': ScanADFF,
            '§dffe': ScanDFFE,
            '§adffe': ScanADFFE,
        }
        return mapping[self.instance_type]

    @property
    def verilog_template(self) -> str:
        return 'always @({header}) begin\n\t{set_out}\nend'

    @property
    def _verilog_clk(self) -> str:
        """
        The verilog representation of the clock sensitivity list entry.

        Has the form `posedge clk_net_name` or `negedge clk_net_name`, depending on the clock polarity.
        """
        return self._v_header(self.clk_port, self.clk_polarity)

    @property
    def verilog_context_map(self) -> SafeFormatDict:
        context_map = super().verilog_context_map
        context_map.update(header=self._verilog_clk, set_out=self._storage_assigns())
        return context_map

    @property
    def verilog(self) -> str:
        return self.verilog_template.format_map(self.verilog_context_map)

    def get_scanff(self) -> 'ScanDFF':
        """
        Creates and returns a scan-DFF version of this DFF, copying all parameters of this DFF.

        No connections are copied however, and the instance initially does not belong to any module.
        """
        self.update_parameters()
        return self.scan_ff_equivalent(name=self.name + '_scan', parameters=self.parameters)

    def evaluate(self) -> None:
        """
        Evaluates the gate's output signal.

        This method is called when the gate's input signals change, and it updates the gate's output signal accordingly.
        """
        self._init_out()
        self._evaluate()

    def _init_out(self) -> None:
        if len(self._curr_out) < self.data_width:
            self._curr_out += [Signal.UNDEFINED] * (self.data_width - len(self._curr_out))

    def _evaluate(self) -> None:
        if self._ff_should_update():
            for i in range(self.data_width):
                self._set_output(new_signals=self._calc_output())

    def _ff_should_update(self) -> bool:
        clk_corr_pol = self.clk_port.signal is self.clk_polarity
        should_update = ('CLK' not in self.prev_signals or self.clk_port.signal != self.prev_signals['CLK'][0]) and clk_corr_pol
        self.prev_signals = self.signals
        return should_update

    def _calc_output(self) -> SignalArray:
        """
        Calculates the gate's output signal.

        For a D flip-flop, the output signal is the input signal when the clock signal has a rising edge and the enable signal is high.
        Otherwise, the output signal is the previous output signal.

        Args:
            idx (int, optional): The idx of the output signal. Defaults to 0.

        Returns:
            Signal: The output signal value.
        """
        return SignalArray(
            signals={
                idx: self.input_port[idx].signal if self.input_port[idx].signal.is_defined else Signal.UNDEFINED for idx in range(self.data_width)
            }
        )


class ADFF(RstMixin, DFF):  # type: ignore[misc]
    """Asynchronously resettable DFF."""

    instance_type: str = f'{CFG.id_internal}adff'

    @property
    def _verilog_header(self) -> str:
        return f'{self._verilog_clk} or {super()._verilog_header}'

    def _ff_should_update(self) -> bool:
        should_update_rst = ('RST' not in self.prev_signals or self.rst_port.signal != self.prev_signals['RST'][0]) and self.in_reset
        should_update_super = super()._ff_should_update() and not self.in_reset
        return should_update_super or should_update_rst


class DFFE(EnMixin, DFF):  # type: ignore[misc]
    """DFF with enable port."""

    instance_type: str = f'{CFG.id_internal}dffe'


class ADFFE(DFFE, ADFF):  # type: ignore[misc]
    """Asynchronously resettable DFF with enable port."""

    instance_type: str = f'{CFG.id_internal}adffe'

    @property
    def verilog_template(self) -> str:
        return super().verilog_template.replace('begin\n\t\tif ({en}) begin\n\t\t{set_out}\n\tend', 'if ({en}) begin\n\t\t{set_out}')

    def _calc_output(self) -> SignalArray:
        if self.rst_port.signal is self.rst_polarity:
            return SignalArray(signals={idx: self.rst_val[idx] for idx in range(self.data_width)})
        return super()._calc_output()


class SDFF(RstMixin, DFF):  # type: ignore[misc]
    """Synchronously resettable DFF."""

    instance_type: str = f'{CFG.id_internal}sdff'

    @property
    def _verilog_header(self) -> str:
        return self._verilog_clk

    @property
    def verilog_template(self) -> str:
        return 'always @({header}) begin\n\tif ({is_rst}) begin\n\t\t{rst_out}\n\tend else begin\n\t\t{set_out}\n\tend\nend'

    def set_rst(self, new_signal: SignalOrLogicLevel) -> None:
        self.set(self.rst_port.name, new_signal)


class SDFFCE(EnMixin, SDFF):  # type: ignore[misc]
    """Synchronously resettable DFF with enable port, where the enable signal takes precedence over the reset signal."""

    instance_type: str = f'{CFG.id_internal}sdffce'

    @property
    def verilog_template(self) -> str:
        return 'always @({header}) begin\n\tif ({en}) begin\n\t\tif ({is_rst}) begin\n\t\t\t{rst_out}\n\t\tend else begin\n\t\t\t{set_out}\n\t\tend\n\tend\nend'

    def _calc_output(self) -> SignalArray:
        if self.en_port.signal is self.en_polarity:
            if self.rst_port.signal is self.rst_polarity:
                return SignalArray(signals={idx: self.rst_val[idx] for idx in range(self.data_width)})
            return super()._calc_output()
        return SignalArray(signals={idx: self.output_port.signal_array[idx] for idx in range(self.data_width)})


class SDFFE(EnMixin, SDFF):  # type: ignore[misc]
    """Synchronously resettable DFF with enable port, where the reset signal takes precedence over the enable signal."""

    instance_type: str = f'{CFG.id_internal}sdffe'

    @property
    def verilog_template(self) -> str:
        return 'always @({header}) begin\n\tif ({is_rst}) begin\n\t\t{rst_out}\n\tend else if ({en}) begin\n\t\t{set_out}\n\tend\nend'

    def _calc_output(self) -> SignalArray:
        if self.rst_port.signal is self.rst_polarity:
            return SignalArray(signals={idx: self.rst_val[idx] for idx in range(self.data_width)})
        if self.en_port.signal is self.en_polarity:
            return super()._calc_output()
        return SignalArray(signals={idx: self.output_port.signal_array[idx] for idx in range(self.data_width)})


class ALDFF(LoadMixin, DFF):  # type: ignore[misc]
    """Asynchronously load DFF, with a load-enable (AL) and load-data (AD) port."""

    instance_type: str = f'{CFG.id_internal}aldff'

    def _ff_should_update(self) -> bool:
        should_update_rst = ('AL' not in self.prev_signals or self.al_port.signal != self.prev_signals['AL'][0]) and self.in_load
        should_update_super = super()._ff_should_update() and not self.in_load
        return should_update_super or should_update_rst


class ALDFFE(EnMixin, ALDFF):  # type: ignore[misc]
    """Asynchronously load DFF, with a load-enable (AL) and load-data (AD) port and an additional enable port for the default case."""

    instance_type: str = f'{CFG.id_internal}aldffe'

    @property
    def verilog_template(self) -> str:
        return 'always @({header}) begin\n\tif ({is_al}) begin\n\t\t{ad}\n\tend else if ({en}) begin\n\t\t{set_out}\n\tend\nend'

    def _calc_output(self) -> SignalArray:
        if self.al_port.signal is self.load_polarity:
            return SignalArray(signals={idx: self.load_val[idx] for idx in range(self.data_width)})
        if self.en_port.signal is self.en_polarity:
            return super()._calc_output()
        return SignalArray(signals={idx: self.output_port[idx].signal for idx in range(self.data_width)})


class DFFSR(SRMixin, DFF):  # type: ignore[misc]
    instance_type: str = f'{CFG.id_internal}dffsr'

    _prev_signals_sr: Dict[str, SignalArray] = {}

    @property
    def verilog_template(self) -> str:
        return 'always @({header}) begin\n\tif ({is_clr}) begin\n\t\t{clr_out}\n\tend else if ({is_set}) begin\n\t\t{set_out}\n\tend else begin\n\t\t{d_out}\n\tend\nend'

    def _verilog_header_sr(self, idx: int) -> str:
        return self._v_header(self.clk_port, self.clk_polarity) + ' or ' + super()._verilog_header_sr(idx)

    def _evaluate(self) -> None:
        for i in range(self.data_width):
            if self._ff_should_update(i):
                new_signals = {i: self._calc_output().signals[i]}
                self._set_output(new_signals=new_signals)
        self._prev_signals_sr = self.signals

    def _ff_should_update(self, idx: int = 0) -> bool:
        self.prev_signals = self._prev_signals_sr
        should_update_super = super()._ff_should_update()
        clr_active = self.clr_port[idx].signal is self.clr_polarity
        set_active = self.set_port[idx].signal is self.set_polarity
        should_update_clr = ('CLR' not in self._prev_signals_sr or self.clr_port[idx].signal != self._prev_signals_sr['CLR'][idx]) and clr_active
        should_update_set = ('SET' not in self._prev_signals_sr or self.set_port[idx].signal != self._prev_signals_sr['SET'][idx]) and set_active
        return should_update_super or should_update_clr or should_update_set


class DFFSRE(EnMixin, DFFSR):  # type: ignore[misc]
    instance_type: str = f'{CFG.id_internal}dffsre'

    @property
    def verilog_template(self) -> str:
        return 'always @({header}) begin\n\tif ({is_clr}) begin\n\t\t{clr_out}\n\tend else if ({is_set}) begin\n\t\t{set_out}\n\tend else if ({en}) begin\n\t\t{d_out}\n\tend\nend'

    def model_post_init(self, __context: object) -> None:
        super().model_post_init(__context)
        if self.width > 1:  # EnMixin initializes EN port as 1 bit wide, so we have to extend it manually here if required
            self.connect('EN', None, direction=Direction.IN, width=self.width - 1, index=1)

    def _calc_output(self) -> SignalArray:
        signals = {}
        for idx in range(self.data_width):
            if self.clr_port[idx].signal is self.clr_polarity:
                signals[idx] = Signal.LOW
            elif self.set_port[idx].signal is self.set_polarity:
                signals[idx] = Signal.HIGH
            elif self.en_port[idx].signal.is_undefined or (self.en_port[idx].signal is self.en_polarity and self.input_port[idx].signal.is_undefined):
                signals[idx] = Signal.UNDEFINED
            elif self.en_port[idx].signal is self.en_polarity:
                signals[idx] = self.input_port[idx].signal
            else:
                signals[idx] = self.output_port[idx].signal
        return SignalArray(signals=signals)

    def set_en(self, new_signal: SignalOrLogicLevel, idx: Union[int, List[int]] = 0) -> None:
        """
        Sets the enable signal.

        Args:
            new_signal (Signal): The new enable signal value.
            idx (Union[int, List[int]], optional): The index (or indices) to apply the given signal to.
                Can either be an integer (single index to set) or an iterable of integers (e.g. a list of indices).
                For every integer of the iterable the signal value of the corresponding port index is set to the given `new_signal`.
                Defaults to 0.
        """
        self.set('EN', new_signal, idx)


class ScanDFF(ScanMixin, DFF):  # type: ignore[misc] # MRO is fine. Silence, MyPy!
    instance_type: str = f'{CFG.id_internal}scan_dff'


class ScanADFF(ScanMixin, ADFF):  # type: ignore[misc] # MRO is fine. Silence, MyPy!
    instance_type: str = f'{CFG.id_internal}scan_adff'


class ScanDFFE(ScanMixin, DFFE):  # type: ignore[misc] # MRO is fine. Silence, MyPy!
    instance_type: str = f'{CFG.id_internal}scan_dffe'


class ScanADFFE(ScanMixin, ADFFE):  # type: ignore[misc] # MRO is fine. Silence, MyPy!
    instance_type: str = f'{CFG.id_internal}scan_adffe'


class DLatch(EnMixin, StorageGate, BaseModel):
    instance_type: str = f'{CFG.id_internal}dlatch'

    parameters: DLatchParams = DLatchParams()

    @property
    def verilog_template(self) -> str:
        return 'always @(*) begin\n\tif ({en}) begin\n{assignments}\n\tend\nend'

    @property
    def verilog(self) -> str:
        en = self.p2v(self.en_port)
        en = f'~{en}' if self.en_polarity is Signal.LOW else en
        exclude_indices = self._get_unconnected_idx(self.output_port)
        assignments = f'\t\t{self.p2v(self.output_port, exclude_indices)} = {self.p2v(self.input_port, exclude_indices)};'
        return self.verilog_template.format(en=en, assignments=assignments)

    def _calc_output(self) -> SignalArray:
        if self.en_signal == self.en_polarity:
            return SignalArray(signals={idx: self.input_port.signal_array[idx] for idx in range(self.data_width)})
        return SignalArray(signals={idx: self.output_port.signal_array[idx] for idx in range(self.data_width)})


def get(instance_type: str) -> Union[type[PrimitiveGate], None]:
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
    from netlist_carpentry.utils.gate_lib_extras import _build_gate_lib_map as _extras_build_gate_lib_map

    clsmembers: List[Tuple[str, type]] = inspect.getmembers(sys.modules[__name__], inspect.isclass)
    for _, c in clsmembers:
        # Iterate through all class members (i.e. all gates),
        # filter out all classes not being gates
        try:
            # Only works if a class extends _Primitive gate and will raise an exception otherwise
            c_inst: Instance = c(name='', module=Module(name=''))

            # Add the found class to the gate_lib_map
            _gate_lib_map[c_inst.instance_type] = c
        except Exception:  # noqa: PERF203 YES, catching exceptions inside a loop might be bad, I just DONT CARE
            pass
    _gate_lib_map.update(_extras_build_gate_lib_map())
