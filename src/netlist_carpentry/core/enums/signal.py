"""An enumeration representing possible states of a digital signal (0, 1, x, z)."""

from enum import Enum
from typing import Dict, List, Literal, Optional, Union

from pydantic import PositiveInt

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

    @staticmethod
    def get(sval: Union[str, int]) -> 'Signal':
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
        from netlist_carpentry import Signal

        if self.is_defined:
            return Signal.HIGH if self is Signal.LOW else Signal.LOW
        return Signal.UNDEFINED

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
            {0: <Signal.HIGH>, 1: <Signal.LOW>, 2: <Signal.HIGH>}

            >>> # -1 in 4-bit two's complement is 1111
            >>> Signal.from_int(-1, fixed_width=4)
            {0: <Signal.HIGH>, 1: <Signal.HIGH>, 2: <Signal.HIGH>, 3: <Signal.HIGH>}
        """
        # Produces the two-s complement for negative ints
        if sig_val < 0:
            width = fixed_width if fixed_width is not None else len(bin(abs(sig_val))[2:])
            sig_bin_str = format(sig_val & ((1 << width) - 1), f'0{width}b')
        else:
            sig_bin_str = str(bin(sig_val))[2:]  # Cut off the 0b at the start
        return Signal.from_bin(sig_bin_str, msb_first, fixed_width)

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
            Cannot convert signal dict to integer: At least one entry is neither Signal.HIGH nor Signal.LOW,
            dict is {0: Signal.HIGH, 1: Signal.UNDEFINED, 2: Signal.HIGH}!
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
            Cannot convert signals to integer or binary value: At least one entry is neither Signal.HIGH nor Signal.LOW,
            dict is {2: Signal.HIGH, 1: Signal.UNDEFINED, 0: Signal.HIGH}!
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
            {0: <Signal.FLOATING>, 1: <Signal.UNDEFINED>, 2: <Signal.LOW>, 3: <Signal.HIGH>}

            >>> # Parsing with a fixed width (padding)
            >>> Signal.from_bin("11", fixed_width=4)
            {0: <Signal.HIGH>, 1: <Signal.HIGH>, 2: <Signal.LOW>, 3: <Signal.LOW>}
        """
        if any(s not in ['0', '1', 'z', 'x'] for s in sig_str):
            raise ValueError(
                f'Cannot transform signal string into signal array: found illegal character in string {sig_str} (may only contain 0, 1, x and z)'
            )
        if fixed_width is not None:
            sig_str = sig_str.zfill(fixed_width)[-fixed_width:]
        if msb_first:
            sig_str = ''.join(reversed(sig_str))
        sig_dict: Dict[int, 'Signal'] = {}
        for idx, bin_val in enumerate(sig_str):
            new_sig_val = Signal.get(bin_val)
            sig_dict[idx] = new_sig_val
        return sig_dict

    @staticmethod
    def to_bin(sig_list: List['Signal'], msb_first: bool = True) -> str:
        """
        Converts a list of signals to a binary value.

        The signals in the list are assumed to represent binary digits, where Signal.HIGH is 1 and Signal.LOW is 0.
        If all signals in the list are defined (i.e., either HIGH or LOW), this method returns the corresponding binary value.
        Otherwise, it raises a ValueError.

        Args:
            sig_list (List[Signal]): A list of signals representing binary digits.
            msb_first (bool): Whether to interpret the bits as most significant bit first. Defaults to True.

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
            Cannot convert signals to integer or binary value: At least one entry is neither Signal.HIGH nor Signal.LOW,
            dict is {2: Signal.HIGH, 1: Signal.UNDEFINED, 0: Signal.HIGH}!
        """
        # Since enumerate starts from 0, the dict is LSB-first, so 'msb_first' must be inverted
        return Signal.dict_to_bin({i: s for i, s in enumerate(sig_list)}, not msb_first)

    @staticmethod
    def dict_to_bin(signal_dict: Dict[int, 'Signal'], msb_first: bool = True) -> str:
        """
        Converts a dictionary of signals to a binary value.

        The signals in the dictionary are assumed to represent binary digits, where Signal.HIGH is 1 and Signal.LOW is 0.
        If all signals in the dictionary are defined (i.e., either HIGH or LOW), this method returns the corresponding binary value.
        Otherwise, it raises a ValueError.

        Args:
            signal_dict (Dict[int, Signal]): A dictionary of Signal enums representing binary digits, where keys represent bit positions.
            msb_first (bool): Whether to interpret the bits as most significant bit first. Defaults to True.

        Returns:
            int: The binary value represented by the signal dictionary.

        Example:
            >>> signals = {0: Signal.HIGH, 1: Signal.LOW, 2: Signal.HIGH, 3: Signal.HIGH} # LSB: 1011, MSB: 1101 -> 13
            >>> Signal.dict_to_int(signals)
            '1101'
            >>> Signal.dict_to_int(signals, msb_first=False)
            '1011'
            >>> signals_undefined = {0: Signal.HIGH, 1: Signal.UNDEFINED, 2: Signal.HIGH}
            >>> try:
            ...     Signal.dict_to_int(signals_undefined)
            ... except ValueError as e:
            ...     print(e)
            Cannot convert signals to integer or binary value: At least one entry is neither Signal.HIGH nor Signal.LOW,
            dict is {2: Signal.HIGH, 1: Signal.UNDEFINED, 0: Signal.HIGH}!
        """
        if not signal_dict:
            return '0'
        if any(s.is_undefined for s in signal_dict.values()):
            raise ValueError(
                f'Cannot convert signals to integer or binary value: At least one entry is neither Signal.HIGH nor Signal.LOW, dict is {signal_dict}!'
            )
        max_index = max(signal_dict.keys())
        binary_list = ['0'] * (max_index + 1)

        for index, signal in signal_dict.items():
            binary_list[index] = signal.value

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
