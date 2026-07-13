from typing import Dict, Generator, ItemsView, KeysView, List, Optional, Union, ValuesView

from pydantic import BaseModel, NonNegativeInt, PositiveInt

from netlist_carpentry import Signal
from netlist_carpentry.core.exceptions import InvalidSignalError

SIGNAL_LIKE = Union[bool, int, str, Signal]


class SignalArray(BaseModel):
    signals: Dict[NonNegativeInt, Signal]
    signed: bool = False
    msb_first: bool = True
    default_fill: Signal = Signal.UNDEFINED

    @property
    def size(self) -> NonNegativeInt:
        return max(self.signals.keys()) + 1 if self.signals else 0

    @property
    def is_defined(self) -> bool:
        """Whether the whole signal array contains only defined values.

        True, if every element is either `Signal.LOW` or `Signal.HIGH`.
        False, if at least one element is `Signal.FLOATING` or `Signal.UNDEFINED`.
        Also False, if the signal array is empty.

        If `SignalArray.is_defined` is True, `int(SignalArray)` is possible.
        Otherwise, an InvalidSignalError will be raised.
        """
        if self.signals:
            return all(s.is_defined for s in self.signals.values())
        return False

    @property
    def is_undefined(self) -> bool:
        """Whether the whole signal array contains only undefined values.

        True, if every element is either `Signal.FLOATING` or `Signal.UNDEFINED`.
        False, if at least one element is `Signal.LOW` or `Signal.HIGH`.
        Also False, if the signal array is empty.
        """
        if self.signals:
            return all(s.is_undefined for s in self.signals.values())
        return False

    def model_post_init(self, context: object) -> None:
        SignalArray.fill_gaps(self.signals, self.default_fill)
        return super().model_post_init(context)

    def __getitem__(self, key: NonNegativeInt) -> Signal:
        if key in self.signals:
            return self.signals[key]
        raise KeyError(f'No index {key} in Signal array {str(self)!r} (size {self.size})!')

    def __setitem__(self, key: NonNegativeInt, value: Signal) -> None:
        self.signals[key] = value

    def __invert__(self) -> 'SignalArray':
        array = self.model_copy()
        array.signals = {i: ~s for i, s in array.signals.items()}
        return array

    def __int__(self) -> int:
        if self.is_defined:
            val = sum(1 << i for i in self.signals if self[i] is Signal.HIGH)
            if self.signed and val & (1 << (self.size - 1)):  # Two's complement, sign bit is 1 → negative
                val -= 1 << self.size  # subtract 2**n
            return val
        raise InvalidSignalError(f'Cannot convert signal string {str(self)!r} to an integer!')

    def __lshift__(self, other: object) -> 'SignalArray':
        array = self.model_copy()
        if not isinstance(other, (int, SignalArray)):
            raise TypeError(f'Can only shift SignalArrays by int or another SignalArray, not {type(other)!r}!')
        try:
            shift_amount = int(other)
        except ValueError:
            raise InvalidSignalError(f'Cannot shift SignalArray by {other}: SignalArray does not represent a valid integer!')
        array.signals = {idx: self[idx - shift_amount] if idx - shift_amount in self else Signal.LOW for idx in range(self.size)}
        return array

    def __rshift__(self, other: object) -> 'SignalArray':
        array = self.model_copy()
        if not isinstance(other, (int, SignalArray)):
            raise TypeError(f'Can only shift SignalArrays by int or another SignalArray, not {type(other)!r}!')
        try:
            shift_amount = int(other)
        except ValueError:
            raise InvalidSignalError(f'Cannot shift SignalArray by {other}: SignalArray does not represent a valid integer!')
        padding = Signal.HIGH if self.signed and self[max(self.keys())] is Signal.HIGH and shift_amount >= 0 else Signal.LOW
        array.signals = {idx: self[idx + shift_amount] if idx + shift_amount in self else padding for idx in range(self.size)}
        return array

    def __iter__(self) -> Generator[int, None, None]:  # type: ignore[override]
        return iter(k for k in self.signals.keys())

    def __str__(self) -> str:
        step = -1 if self.msb_first else 1
        start = self.size - 1 if self.msb_first else 0
        stop = -1 if self.msb_first else self.size
        return ''.join([self.signals[i].value for i in range(start, stop, step)])

    def items(self) -> ItemsView[int, Signal]:
        return self.signals.items()

    def keys(self) -> KeysView[int]:
        return self.signals.keys()

    def values(self) -> ValuesView[Signal]:
        return self.signals.values()

    @staticmethod
    def fill_gaps(signals: Dict[NonNegativeInt, Signal], default: Signal = Signal.UNDEFINED) -> None:
        if signals:
            highest = max(signals.keys())
            for i in range(highest):
                if i not in signals:
                    signals[i] = default

    @classmethod
    def parsable(cls, signal_like: object) -> bool:
        if isinstance(signal_like, Signal):
            return True
        if isinstance(signal_like, int):
            return True
        if isinstance(signal_like, str) and all(c in ['0', '1', 'x', 'z'] for c in signal_like):
            return True
        if isinstance(signal_like, list):
            return all(Signal.parsable(s) for s in signal_like)
        if isinstance(signal_like, dict):
            keys_pos_int = all(isinstance(k, int) and k >= 0 for k in signal_like)
            return keys_pos_int and all(Signal.parsable(s) for s in signal_like.values())
        return False

    @classmethod
    def create(cls, value: Union[SIGNAL_LIKE, List[SIGNAL_LIKE], Dict[int, SIGNAL_LIKE]], default_fill: Signal = Signal.UNDEFINED) -> 'SignalArray':
        if isinstance(value, dict):
            if all(isinstance(k, int) and k >= 0 for k in value):
                signals = {k: Signal.get(v) for k, v in value.items()}
                return SignalArray(signals=signals, default_fill=default_fill)
            raise InvalidSignalError(f'The given dictionary cannot be translated to a valid signal array! The dictionary is {value!r}')
        if isinstance(value, list):
            signals = {i: Signal.get(v) for i, v in enumerate(value)}
            return SignalArray(signals=signals, default_fill=default_fill)
        if isinstance(value, int):
            signal_array = cls.from_int(value)
            signal_array.default_fill = default_fill
            return signal_array
        if isinstance(value, str):
            signal_array = cls.from_bin(value)
            signal_array.default_fill = default_fill
            return signal_array
        return SignalArray(signals={}, default_fill=default_fill)

    @classmethod
    def from_int(cls, sig_val: int, msb_first: bool = True, fixed_width: Optional[PositiveInt] = None, truncate: bool = False) -> 'SignalArray':
        """
        Converts an integer value into a SignalArray object.

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
            fixed_width (Optional[PositiveInt], optional): The desired bit-width. Defaults to None.
                - For negative numbers, this defines the wrap-around point for the
                  two's complement logic.
                - If the integer requires fewer bits than `fixed_width`, the resulting
                  signal will be zero-padded (or sign-extended for negatives).
                - If the integer requires more bits, it will be truncated if `truncate` is `True`,
                  otherwise a ValueError is raised.
                - If None, the minimum number of bits required to represent the value of `sig_val` is used.
            truncate (bool, optional): Whether to truncate the signal array, if `fixed_width` is smaller than
                the minimum required size. Only in this case will the parameter have any effect.
                If True, it truncates the highest bits until the size matches `fixed_width`.
                If False, a ValueError is raised. Defaults to False.

        Returns:
            SignalArray: A SignalArray object, where the keys of the`signals` dictionary are integer indices
                (starting from 0 for the LSB) and the values are the corresponding Signal objects.

        Example:
            >>> # 5 in binary is 101. MSB-first mapping:
            >>> SignalArray.from_int(5).signals
            {0: HIGH, 1: LOW, 2: HIGH}

            >>> # -1 in 4-bit two's complement is 1111
            >>> SignalArray.from_int(-1, fixed_width=4).signals
            {0: HIGH, 1: HIGH, 2: HIGH, 3: HIGH}
        """
        min_width = (sig_val if sig_val >= 0 else ~sig_val).bit_length() + (1 if sig_val < 0 else 0)
        if fixed_width is not None and fixed_width < min_width and not truncate:
            raise ValueError(f"'fixed_width' of {fixed_width!r} is too small for value {sig_val} (requires {min_width} bits)!")
        # Produces the two-s complement for negative ints
        width = fixed_width if fixed_width is not None else min_width
        mask = (1 << width) - 1
        sig_bin_str = f'{sig_val & mask:0{width}b}'
        sig_bin_str = ''.join(s for s in reversed(sig_bin_str)) if not msb_first else sig_bin_str
        return SignalArray.from_bin(sig_bin_str, msb_first, fixed_width, sig_val < 0)

    @classmethod
    def from_bin(
        cls, sig_str: str, msb_first: bool = True, fixed_width: Optional[PositiveInt] = None, signed: bool = False, truncate: bool = False
    ) -> 'SignalArray':
        """
        Parses a digital signal string and maps it to a SignalArray object.

        This method converts a string representation of a multi-bit signal (e.g., "10xz") into a SignalArray object.
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
            signed (bool, optional): Whether the given string represents a signed number or not.
                Defaults to False, meaning unsigned.
            truncate (bool, optional): Whether to truncate the signal array, if `fixed_width` is smaller than
                the minimum required size. Only in this case will the parameter have any effect.
                If True, it truncates the highest bits until the size matches `fixed_width`.
                If False, a ValueError is raised. Defaults to False.

        Returns:
            SignalArray: A SignalArray object, where the keys of the`signals` dictionary are integer indices
                (starting from 0 for the LSB) and the values are the corresponding Signal objects.

        Raises:
            InvalidSignalError: If `sig_str` contains characters other than '0', '1', 'x', or 'z'.

        Example:
            >>> # Parsing a 4-bit MSB-first signal
            >>> SignalArray.from_bin("10xz", msb_first=True).signals
            {0: FLOATING, 1: UNDEFINED, 2: LOW, 3: HIGH}

            >>> # Parsing with a fixed width (padding)
            >>> SignalArray.from_bin("11", fixed_width=4).signals
            {0: HIGH, 1: HIGH, 2: LOW, 3: LOW}
        """
        if any(s not in ['0', '1', 'z', 'x'] for s in sig_str):
            raise InvalidSignalError(
                f'Cannot transform signal string into signal array: found illegal character in string {sig_str} (may only contain 0, 1, x and z)'
            )
        if fixed_width is not None:
            if fixed_width < len(sig_str) and not truncate:
                raise ValueError(f"'fixed_width' of {fixed_width!r} is too small for string {sig_str} (requires {len(sig_str)} bits)!")
            sign_char = sig_str[0] if msb_first else sig_str[-1]
            fill_char = '0' if not signed or sign_char == '0' else '1'
            sig_str = sig_str.rjust(fixed_width, fill_char)[-fixed_width:]
        sig_str = ''.join(reversed(sig_str)) if msb_first else sig_str
        sig_dict = {idx: Signal.get(bin_val) for idx, bin_val in enumerate(sig_str)}
        return SignalArray(signals=sig_dict, msb_first=msb_first, signed=signed)
