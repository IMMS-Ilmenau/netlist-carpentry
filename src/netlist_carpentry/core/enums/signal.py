"""An enumeration representing possible states of a digital signal (0, 1, x, z)."""

import warnings
from enum import Enum
from typing import Dict, List, Literal, Optional, Union

from pydantic import PositiveInt

from netlist_carpentry.core.exceptions import SignalError

T_SIGNAL_STATES = Literal['0', '1', 'z', 'x']


class Signal(Enum):
    """An enumeration representing possible states of a digital signal.

    The following states are defined:
    - LOW: A logical zero or a voltage level close to ground.
    - HIGH: A logical one or a voltage level close to the supply voltage.
    - FLOATING: The signal is floating (high-impedance), represented by 'z'.
    - UNDEFINED: The signal state cannot be determined, represented by 'x'.

    These states are commonly used in digital electronics and circuit design.
    """

    LOW = '0'
    """A logical zero or a voltage level close to ground."""

    HIGH = '1'
    """A logical one or a voltage level close to the supply voltage."""

    FLOATING = 'z'
    """The signal is floating (high-impedance)."""

    UNDEFINED = 'x'
    """The signal state cannot be determined."""

    @classmethod
    def parsable(cls, signal_like: object) -> bool:
        """Returns True if the given signal_like object can be translated into an object from this enum.

        If True, the given object can be translated into a signal via `Signal.get(object)`.
        If False, `Signal.get(object)` returns `Signal.UNDEFINED`.

        Parseable signal_like objects are the integers `0` and `1`, the strings `'0'`, `'1'`, `'x'` and `'z'`,
        boolean values `True` and `False`, as well as objects from this enum (e.g. `Signal.HIGH`).

        Args:
            signal_like (object): The object to check whether it conforms to an object from this enum.
                Parseable signal_like objects are the integers `0` and `1`, the strings `'0'`, `'1'`, `'x'` and `'z'`,
                boolean values `True` and `False`, as well as objects from this enum (e.g. `Signal.HIGH`).

        Returns:
            bool: True, if the given object can be translated into a signal via `Signal.get(object)`. False otherwise.
        """
        if isinstance(signal_like, Signal):
            return True
        if signal_like in [0, 1, '0', '1', 'x', 'z', 'X', 'Z', True, False]:
            return True
        return False

    @staticmethod
    def get(sval: Union[str, int, bool, 'Signal']) -> 'Signal':
        """
        This method is used to get the Signal corresponding to the given string or integer value.

        It can be used to convert a string or integer representation of a digital signal to its corresponding Signal enum.

        For example, Signal.get('0'), Signal.get(0) and Signal.get(False) return Signal.LOW,
        Signal.get('1'), Signal.get(1) and Signal.get(True) returns Signal.HIGH,
        Signal.get('z') or Signal.get('Z') return Signal.FLOATING, and any other input returns Signal.UNDEFINED.

        This method also accepts boolean values as inputs (since bool is a subclass of int), so calling Signal.get()
        with a boolean expression like `val_a & val_b` is also valid.

        Args:
            sval (Union[str, int]): The string or integer value to be converted to a Signal enum.
                Boolean expressions are also allowed.

        Returns:
            Signal: The Signal enum corresponding to the given string or integer value.
        """
        if isinstance(sval, bool):
            sval = int(sval)
        sval_str = str(sval).lower()
        if sval_str in ['0', '1', 'z']:
            return Signal(sval_str)
        return Signal.UNDEFINED

    @property
    def is_defined(self) -> bool:
        """
        Checks if the signal is defined, i.e., if it is either logical low or high.

        This method returns True if the signal is defined, i.e., if it is either logical low (0) or logical high (1).
        Otherwise, it returns False, indicating that the signal is either undefined ('x') or unconnected ('z').
        """
        return self.value == '0' or self.value == '1'

    @property
    def is_undefined(self) -> bool:
        """
        Checks if the signal is undefined, i.e., if it is neither logical low nor high.

        This method returns True if the signal is undefined, i.e., if it is either `x` (undefined) or `z` (unconnected).
        Otherwise, it returns False, indicating that the signal is either 0 or 1.
        """
        return not self.is_defined

    def invert(self) -> 'Signal':
        """
        Inverts the signal.

        If the signal is defined, i.e., if it is either logical low (0) or logical high (1),
        this method returns the inverted signal. Otherwise, it returns Signal.UNDEFINED.

        Returns:
            Signal: The inverted signal if the signal is defined, otherwise Signal.UNDEFINED.
        """
        warnings.warn(
            f'Signal.{self.name}.invert() is deprecated and will be removed in v1.0.0. Use ~Signal.{self.name} instead!',
            DeprecationWarning,
            stacklevel=2,
        )
        return ~self

    def __invert__(self) -> 'Signal':
        if self.is_defined:
            return type(self).LOW if self else type(self).HIGH
        return type(self).UNDEFINED

    def __bool__(self) -> bool:
        if self.is_defined:
            return self is Signal.HIGH
        raise SignalError(f'bool({self!r}) is not defined!')

    def __and__(self, other: 'Signal') -> 'Signal':
        if not isinstance(other, Signal):
            return NotImplemented
        if self is Signal.LOW or other is Signal.LOW:
            return Signal.LOW  # 0 AND anything is 0
        if self.is_undefined or other.is_undefined:
            return Signal.UNDEFINED  # X AND anything (except 0) is X
        return Signal.HIGH  # Last case: 1 AND 1 is 1

    def __or__(self, other: 'Signal') -> 'Signal':
        if not isinstance(other, Signal):
            return NotImplemented
        if self is Signal.HIGH or other is Signal.HIGH:
            return Signal.HIGH  # 1 AND anything is 1
        if self.is_undefined or other.is_undefined:
            return Signal.UNDEFINED  # X AND anything (except 1) is X
        return Signal.LOW  # Last case: 0 AND 0 is 0

    def __xor__(self, other: 'Signal') -> 'Signal':
        if not isinstance(other, Signal):
            return NotImplemented
        if self.is_undefined or other.is_undefined:
            return Signal.UNDEFINED  # X XOR anything is X
        return Signal.get(self != other)

    def __int__(self) -> int:
        if self.is_defined:
            return int(self.value)
        raise SignalError(f"Cannot cast 'Signal.{self.name}' to int: Value is {self.value!r}!")

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return str(self.name)

    @staticmethod
    def from_int(sig_val: int, msb_first: bool = True, fixed_width: Optional[PositiveInt] = None) -> Dict[int, 'Signal']:
        """
        Converts an integer value into a dictionary of Signal objects.

        This method acts as a high-level wrapper for :meth:`from_bin`.
        It handles the conversion of standard Python integers (including negative values)
        into a binary string representation before mapping them to signal indices.

        Sign Handling:
            - **Positive Integers:** Converted to their standard binary representation.
            - **Negative Integers:** Converted using **two's complement** representation.
              The bit-width for the two's complement is determined by `fixed_width`.
              If `fixed_width` is not provided, it defaults to the minimum number of
              bits required to represent the absolute value of `sig_val`.

        Args:
            sig_val (int): The integer value to transform. Can be positive or negative.
            msb_first (bool, optional): Determines the bit-indexing direction.
                - If True (default), index 0 is the Least Significant Bit (LSB).
                - This parameter is passed directly to :meth:`from_bin`.
            fixed_width (Optional[PositiveInt], optional): The desired bit-width.
                - For negative numbers, this defines the wrap-around point for the
                  two's complement logic.
                - If the integer requires fewer bits than `fixed_width`, the resulting
                  signal will be zero-padded (or sign-extended for negatives).
                - If the integer requires more bits, it will be truncated.

        Returns:
            Dict[int, Signal]: A dictionary where keys are integer indices (starting from 0
                for the LSB) and values are Signal objects (HIGH or LOW).

        Example:
            >>> # 5 in binary is 101. MSB-first mapping:
            >>> Signal.from_int(5)
            {0: HIGH, 1: LOW, 2: HIGH}

            >>> # -1 in 4-bit two's complement is 1111
            >>> Signal.from_int(-1, fixed_width=4)
            {0: HIGH, 1: HIGH, 2: HIGH, 3: HIGH}
        """
        from netlist_carpentry import SignalArray

        warnings.warn(
            "Signal.from_int() is deprecated and will be removed in v1.0.0. Use SignalArray.from_int() instead! SignalArray can be imported directly from 'netlist_carpentry'.",
            DeprecationWarning,
            stacklevel=2,
        )
        return SignalArray.from_int(sig_val, msb_first, fixed_width).signals

    @staticmethod
    def to_int(sig_list: List['Signal'], msb_first: bool = True, signed: bool = False) -> int:
        """
        Converts a list of signals to an integer.

        The signals in the list are assumed to represent binary digits, where Signal.HIGH is 1 and Signal.LOW is 0.
        If all signals in the list are defined (i.e., either HIGH or LOW), this method returns the corresponding integer value.
        Otherwise, it raises a ValueError.

        Args:
            sig_list (List[Signal]): A list of signals representing binary digits.
            msb_first (bool): Whether to interpret the bits as most significant bit first. Defaults to True.
            signed (bool): Whether the signal value should be interpreted as a signed number (two's complement) or unsigned number. Defaults to False.

        Returns:
            int: The integer value represented by the signal list.

        Example:
            ```python
            >>> signals = [Signal.HIGH, Signal.LOW, Signal.HIGH]
            >>> Signal.to_int(signals)
            5
            >>> signals_undefined = [Signal.HIGH, Signal.UNDEFINED, Signal.HIGH]
            >>> try:
            ...     Signal.to_int(signals_undefined)
            ... except ValueError as e:
            ...     print(e)
            Cannot convert signals to integer or binary value: At least one entry is neither Signal.HIGH nor Signal.LOW, dict is {0: HIGH, 1: UNDEFINED, 2: HIGH}!

            ```
        """
        # Since enumerate starts from 0, the dict is LSB-first, so 'msb_first' must be inverted
        return Signal.dict_to_int({i: s for i, s in enumerate(sig_list)}, not msb_first, signed)

    @staticmethod
    def dict_to_int(signal_dict: Dict[int, 'Signal'], msb_first: bool = True, signed: bool = False) -> int:
        """
        Converts a dictionary of signals to an integer.

        The signals in the dictionary are assumed to represent binary digits, where Signal.HIGH is 1 and Signal.LOW is 0.
        If all signals in the dictionary are defined (i.e., either HIGH or LOW), this method returns the corresponding integer value.
        Otherwise, it raises a ValueError.

        Args:
            signal_dict (Dict[int, Signal]): A dictionary of Signal enums representing binary digits, where keys represent bit positions.
            msb_first (bool): Whether to interpret the bits as most significant bit first. Defaults to True.
            signed (bool): Whether the signal value should be interpreted as a signed number (two's complement) or unsigned number. Defaults to False.

        Returns:
            int: The integer value represented by the signal dictionary.

        Example:
            >>> signals = {0: Signal.HIGH, 1: Signal.LOW, 2: Signal.HIGH, 3: Signal.HIGH} # LSB: 1011, MSB: 1101 -> 13
            >>> Signal.dict_to_int(signals)
            13
            >>> Signal.dict_to_int(signals, msb_first=False)
            11
            >>> signals_undefined = {0: Signal.HIGH, 1: Signal.UNDEFINED, 2: Signal.HIGH}
            >>> try:
            ...     Signal.dict_to_int(signals_undefined)
            ... except ValueError as e:
            ...     print(e)
            Cannot convert signals to integer or binary value: At least one entry is neither Signal.HIGH nor Signal.LOW, dict is {0: HIGH, 1: UNDEFINED, 2: HIGH}!
        """
        binary_string = Signal.dict_to_bin(signal_dict, msb_first)
        decimal_value = int(binary_string, 2)
        if signed and binary_string[0] == '1':
            decimal_value -= 1 << len(binary_string)
        return decimal_value

    @staticmethod
    def from_bin(sig_str: str, msb_first: bool = True, fixed_width: Optional[PositiveInt] = None) -> Dict[int, 'Signal']:
        """
        Parses a digital signal string and maps it to a dictionary of Signal objects indexed by bit position.

        This method converts a string representation of a multi-bit signal (e.g., "10xz") into a structured dictionary.
        It handles bit-ordering (MSB vs LSB), allows fixed bit-widths (padding or truncation),
        and validates that the input string contains only valid digital logic characters.

        Args:
            sig_str (str): A string representing the signal values. Valid characters are:
                - '0': Logic Low
                - '1': Logic High
                - 'z': High Impedance/Tristate
                - 'x': Unknown/Undefined
            msb_first (bool, optional): Determines the bit-indexing direction.
                - If True (default), the character at `sig_str[0]` is treated as the Most
                  Significant Bit (MSB) and assigned the highest index.
                - If False, the character at `sig_str[0]` is treated as the Least
                  Significant Bit (LSB) and assigned index 0.
            fixed_width (Optional[PositiveInt], optional): The desired number of bits.
                - If the resulting string is shorter than `fixed_width`, it is left-padded
                  with '0' (MSB padding).
                - If longer, it is truncated from the left (MSB side).
                - Defaults to None, using the length of `sig_str` as provided.

        Returns:
            Dict[int, Signal]: A dictionary where keys are integer indices (starting from 0
                for the LSB) and values are the corresponding Signal objects.

        Raises:
            ValueError: If `sig_str` contains characters other than '0', '1', 'x', or 'z'.

        Example:
            >>> # Parsing a 4-bit MSB-first signal
            >>> Signal.from_bin("10xz", msb_first=True)
            {0: FLOATING, 1: UNDEFINED, 2: LOW, 3: HIGH}

            >>> # Parsing with a fixed width (padding)
            >>> Signal.from_bin("11", fixed_width=4)
            {0: HIGH, 1: HIGH, 2: LOW, 3: LOW}
        """
        from netlist_carpentry import SignalArray

        warnings.warn(
            "Signal.from_bin() is deprecated and will be removed in v1.0.0. Use SignalArray.from_bin() instead! SignalArray can be imported directly from 'netlist_carpentry'.",
            DeprecationWarning,
            stacklevel=2,
        )
        return SignalArray.from_bin(sig_str, msb_first, fixed_width).signals

    @staticmethod
    def to_bin(
        sig_list: List['Signal'], msb_first: bool = True, fixed_width: Optional[PositiveInt] = None, pad_value: Literal['0', '1'] = '0'
    ) -> str:
        """
        Converts a list of signals to a binary value.

        The signals in the list are assumed to represent binary digits, where Signal.HIGH is 1 and Signal.LOW is 0.
        If all signals in the list are defined (i.e., either HIGH or LOW), this method returns the corresponding binary value.
        Otherwise, it raises a ValueError.

        Args:
            sig_list (List[Signal]): A list of signals representing binary digits.
            msb_first (bool): Whether to interpret the bits as most significant bit first. Defaults to True.
            fixed_width (Optional[PositiveInt], optional): The desired number of bits.
                - If the resulting string is shorter than `fixed_width`, it is left-padded
                  with '0' or '1' (depending on the signedness).
                - If longer, it is truncated from the left (MSB side).
                - Defaults to None, using the size of `signal_dict` as provided.
            pad_value (Literal['0', '1'], optional): The value used for padding. May be either 0 or 1. Defaults to 0.

        Returns:
            int: The binary value represented by the signal list.

        Example:
            >>> signals = [Signal.HIGH, Signal.LOW, Signal.HIGH]
            >>> Signal.to_bin(signals)
            '101'
            >>> signals_undefined = [Signal.HIGH, Signal.UNDEFINED, Signal.HIGH]
            >>> try:
            ...     Signal.to_bin(signals_undefined)
            ... except ValueError as e:
            ...     print(e)
            Cannot convert signals to integer or binary value: At least one entry is neither Signal.HIGH nor Signal.LOW, dict is {0: HIGH, 1: UNDEFINED, 2: HIGH}!
        """
        # Since enumerate starts from 0, the dict is LSB-first, so 'msb_first' must be inverted
        return Signal.dict_to_bin({i: s for i, s in enumerate(reversed(sig_list))}, msb_first, fixed_width, pad_value)

    @staticmethod
    def dict_to_bin(
        signal_dict: Dict[int, 'Signal'], msb_first: bool = True, fixed_width: Optional[PositiveInt] = None, pad_value: Literal['0', '1'] = '0'
    ) -> str:
        """
        Converts a dictionary of signals to a binary value.

        The signals in the dictionary are assumed to represent binary digits, where Signal.HIGH is 1 and Signal.LOW is 0.
        If all signals in the dictionary are defined (i.e., either HIGH or LOW), this method returns the corresponding binary value.
        Otherwise, it raises a ValueError.

        Args:
            signal_dict (Dict[int, Signal]): A dictionary of Signal enums representing binary digits, where keys represent bit positions.
            msb_first (bool): Whether to interpret the bits as most significant bit first. Defaults to True.
            fixed_width (Optional[PositiveInt], optional): The desired number of bits.
                - If the resulting string is shorter than `fixed_width`, it is left-padded
                  with '0' or '1' (depending on the signedness).
                - If longer, it is truncated from the left (MSB side).
                - Defaults to None, using the size of `signal_dict` as provided.
            pad_value (Literal['0', '1'], optional): The value used for padding. May be either 0 or 1. Defaults to 0.

        Returns:
            str: The binary value represented by the signal dictionary.

        Example:
            >>> signals = {0: Signal.HIGH, 1: Signal.LOW, 2: Signal.HIGH, 3: Signal.HIGH} # LSB: 1011, MSB: 1101 -> 13
            >>> Signal.dict_to_bin(signals)
            '1101'
            >>> Signal.dict_to_bin(signals, msb_first=False)
            '1011'
            >>> signals_undefined = {0: Signal.HIGH, 1: Signal.UNDEFINED, 2: Signal.HIGH}
            >>> try:
            ...     Signal.dict_to_bin(signals_undefined)
            ... except ValueError as e:
            ...     print(e)
            Cannot convert signals to integer or binary value: At least one entry is neither Signal.HIGH nor Signal.LOW, dict is {0: HIGH, 1: UNDEFINED, 2: HIGH}!
        """
        if not signal_dict:
            return pad_value
        if any(s.is_undefined for s in signal_dict.values()):
            raise ValueError(
                f'Cannot convert signals to integer or binary value: At least one entry is neither Signal.HIGH nor Signal.LOW, dict is {signal_dict}!'
            )
        width = fixed_width or max(signal_dict.keys()) + 1
        binary_list = [pad_value] * width

        for index, signal in signal_dict.items():
            if index < len(binary_list):
                binary_list[index] = signal.value  # type: ignore[call-overload]

        if msb_first:
            binary_list.reverse()

        return ''.join(binary_list).zfill(len(binary_list))

    @staticmethod
    def twos_complement(sig: int, width: Optional[int] = None, msb_first: bool = True) -> str:
        # Invert the given number
        # Compute -val in the same width or the given width
        if width is None:
            width = len(bin(sig)[2:])
        comp = (-sig) & ((1 << width) - 1)
        comp_str = format(comp, f'0{width}b')
        return comp_str if msb_first else ''.join(reversed(comp_str))
