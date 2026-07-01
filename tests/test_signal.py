import os
import re

import pytest

from netlist_carpentry.core.enums.signal import Signal
from netlist_carpentry.core.exceptions import SignalError


def test_signal_enum_values() -> None:
    assert Signal.LOW.value == '0'
    assert Signal.HIGH.value == '1'
    assert Signal.FLOATING.value == 'z'
    assert Signal.UNDEFINED.value == 'x'


def test_signal_enum_names() -> None:
    assert Signal('0').name == 'LOW'
    assert Signal('1').name == 'HIGH'
    assert Signal('z').name == 'FLOATING'
    assert Signal('x').name == 'UNDEFINED'


def test_signal_enum_invalid_value() -> None:
    with pytest.raises(ValueError):
        Signal(2)


def test_parsable() -> None:
    assert Signal.parsable('0')
    assert Signal.parsable(0)
    assert Signal.parsable(False)
    assert Signal.parsable('1')
    assert Signal.parsable(1)
    assert Signal.parsable(True)
    assert Signal.parsable('z')
    assert Signal.parsable('Z')
    assert Signal.parsable('x')
    assert Signal.parsable('X')
    assert not Signal.parsable(42)
    assert not Signal.parsable('ABC')


def test_get() -> None:
    assert Signal.get('0') is Signal.LOW
    assert Signal.get(0) is Signal.LOW
    assert Signal.get(False) is Signal.LOW
    assert Signal.get('1') is Signal.HIGH
    assert Signal.get(1) is Signal.HIGH
    assert Signal.get(True) is Signal.HIGH
    assert Signal.get('z') is Signal.FLOATING
    assert Signal.get('Z') is Signal.FLOATING
    assert Signal.get('x') is Signal.UNDEFINED
    assert Signal.get(42) is Signal.UNDEFINED
    assert Signal.get('ABC') is Signal.UNDEFINED


def test_is_defined() -> None:
    assert Signal.LOW.is_defined
    assert Signal.HIGH.is_defined
    assert not Signal.FLOATING.is_defined
    assert not Signal.UNDEFINED.is_defined


def test_is_undefined() -> None:
    assert not Signal.LOW.is_undefined
    assert not Signal.HIGH.is_undefined
    assert Signal.FLOATING.is_undefined
    assert Signal.UNDEFINED.is_undefined


def test_invert() -> None:
    with pytest.warns(DeprecationWarning, match=r'Signal.LOW.invert\(\) is deprecated .* v1.0.0. Use ~Signal.LOW'):
        assert Signal.LOW.invert() is Signal.HIGH
    with pytest.warns(DeprecationWarning, match=r'Signal.HIGH.invert\(\) is deprecated .* v1.0.0. Use ~Signal.HIGH'):
        assert Signal.HIGH.invert() is Signal.LOW
    with pytest.warns(DeprecationWarning, match=r'Signal.FLOATING.invert\(\) is deprecated .* v1.0.0. Use ~Signal.FLOATING'):
        assert Signal.FLOATING.invert() is Signal.UNDEFINED
    with pytest.warns(DeprecationWarning, match=r'Signal.UNDEFINED.invert\(\) is deprecated .* v1.0.0. Use ~Signal.UNDEFINED'):
        assert Signal.UNDEFINED.invert() is Signal.UNDEFINED


def test_invert_dunder() -> None:
    assert ~Signal.LOW is Signal.HIGH
    assert ~Signal.HIGH is Signal.LOW
    assert ~Signal.FLOATING is Signal.UNDEFINED
    assert ~Signal.UNDEFINED is Signal.UNDEFINED


def test_bool() -> None:
    assert bool(Signal.LOW) is False
    assert bool(Signal.HIGH) is True
    with pytest.raises(SignalError):
        bool(Signal.FLOATING)
    with pytest.raises(SignalError):
        bool(Signal.UNDEFINED)


def test_and() -> None:
    assert (Signal.LOW & Signal.LOW) is Signal.LOW
    assert (Signal.LOW & Signal.HIGH) is Signal.LOW
    assert (Signal.LOW & Signal.UNDEFINED) is Signal.LOW
    assert (Signal.LOW & Signal.FLOATING) is Signal.LOW
    assert (Signal.HIGH & Signal.LOW) is Signal.LOW
    assert (Signal.HIGH & Signal.HIGH) is Signal.HIGH
    assert (Signal.HIGH & Signal.UNDEFINED) is Signal.UNDEFINED
    assert (Signal.HIGH & Signal.FLOATING) is Signal.UNDEFINED
    assert (Signal.UNDEFINED & Signal.LOW) is Signal.LOW
    assert (Signal.UNDEFINED & Signal.HIGH) is Signal.UNDEFINED
    assert (Signal.UNDEFINED & Signal.UNDEFINED) is Signal.UNDEFINED
    assert (Signal.UNDEFINED & Signal.FLOATING) is Signal.UNDEFINED
    assert (Signal.FLOATING & Signal.LOW) is Signal.LOW
    assert (Signal.FLOATING & Signal.HIGH) is Signal.UNDEFINED
    assert (Signal.FLOATING & Signal.UNDEFINED) is Signal.UNDEFINED
    assert (Signal.FLOATING & Signal.FLOATING) is Signal.UNDEFINED

    with pytest.raises(TypeError):
        False & Signal.LOW
    with pytest.raises(TypeError):
        Signal.LOW & False
    with pytest.raises(TypeError):
        Signal.LOW & '0'
    with pytest.raises(TypeError):
        Signal.LOW & 0


def test_or() -> None:
    assert (Signal.LOW | Signal.LOW) is Signal.LOW
    assert (Signal.LOW | Signal.HIGH) is Signal.HIGH
    assert (Signal.LOW | Signal.UNDEFINED) is Signal.UNDEFINED
    assert (Signal.LOW | Signal.FLOATING) is Signal.UNDEFINED
    assert (Signal.HIGH | Signal.LOW) is Signal.HIGH
    assert (Signal.HIGH | Signal.HIGH) is Signal.HIGH
    assert (Signal.HIGH | Signal.UNDEFINED) is Signal.HIGH
    assert (Signal.HIGH | Signal.FLOATING) is Signal.HIGH
    assert (Signal.UNDEFINED | Signal.LOW) is Signal.UNDEFINED
    assert (Signal.UNDEFINED | Signal.HIGH) is Signal.HIGH
    assert (Signal.UNDEFINED | Signal.UNDEFINED) is Signal.UNDEFINED
    assert (Signal.UNDEFINED | Signal.FLOATING) is Signal.UNDEFINED
    assert (Signal.FLOATING | Signal.LOW) is Signal.UNDEFINED
    assert (Signal.FLOATING | Signal.HIGH) is Signal.HIGH
    assert (Signal.FLOATING | Signal.UNDEFINED) is Signal.UNDEFINED
    assert (Signal.FLOATING | Signal.FLOATING) is Signal.UNDEFINED

    with pytest.raises(TypeError):
        False | Signal.HIGH
    with pytest.raises(TypeError):
        Signal.HIGH | False
    with pytest.raises(TypeError):
        Signal.HIGH | '0'
    with pytest.raises(TypeError):
        Signal.HIGH | 0


def test_xor() -> None:
    assert (Signal.LOW ^ Signal.LOW) is Signal.LOW
    assert (Signal.LOW ^ Signal.HIGH) is Signal.HIGH
    assert (Signal.LOW ^ Signal.UNDEFINED) is Signal.UNDEFINED
    assert (Signal.LOW ^ Signal.FLOATING) is Signal.UNDEFINED
    assert (Signal.HIGH ^ Signal.LOW) is Signal.HIGH
    assert (Signal.HIGH ^ Signal.HIGH) is Signal.LOW
    assert (Signal.HIGH ^ Signal.UNDEFINED) is Signal.UNDEFINED
    assert (Signal.HIGH ^ Signal.FLOATING) is Signal.UNDEFINED
    assert (Signal.UNDEFINED ^ Signal.LOW) is Signal.UNDEFINED
    assert (Signal.UNDEFINED ^ Signal.HIGH) is Signal.UNDEFINED
    assert (Signal.UNDEFINED ^ Signal.UNDEFINED) is Signal.UNDEFINED
    assert (Signal.UNDEFINED ^ Signal.FLOATING) is Signal.UNDEFINED
    assert (Signal.FLOATING ^ Signal.LOW) is Signal.UNDEFINED
    assert (Signal.FLOATING ^ Signal.HIGH) is Signal.UNDEFINED
    assert (Signal.FLOATING ^ Signal.UNDEFINED) is Signal.UNDEFINED
    assert (Signal.FLOATING ^ Signal.FLOATING) is Signal.UNDEFINED

    with pytest.raises(TypeError):
        False ^ Signal.HIGH
    with pytest.raises(TypeError):
        Signal.HIGH ^ False
    with pytest.raises(TypeError):
        Signal.HIGH ^ '0'
    with pytest.raises(TypeError):
        Signal.HIGH ^ 0


def test_int() -> None:
    assert int(Signal.LOW) == 0
    assert int(Signal.HIGH) == 1
    with pytest.raises(SignalError):
        int(Signal.FLOATING)
    with pytest.raises(SignalError):
        int(Signal.UNDEFINED)


def test_str() -> None:
    assert str(Signal.LOW) == '0'
    assert str(Signal.HIGH) == '1'
    assert str(Signal.FLOATING) == 'z'
    assert str(Signal.UNDEFINED) == 'x'


def test_repr() -> None:
    assert repr(Signal.LOW) == 'LOW'
    assert repr(Signal.HIGH) == 'HIGH'
    assert repr(Signal.FLOATING) == 'FLOATING'
    assert repr(Signal.UNDEFINED) == 'UNDEFINED'


def test_from_int() -> None:
    with pytest.warns(
        DeprecationWarning,
        match=re.escape(
            "Signal.from_int() is deprecated and will be removed in v1.0.0. Use SignalArray.from_int() instead! SignalArray can be imported from 'netlist_carpentry.core.types'"
        ),
    ):
        assert Signal.from_int(0) == {0: Signal.LOW}
        assert Signal.from_int(1) == {0: Signal.HIGH}
        assert Signal.from_int(2) == {1: Signal.HIGH, 0: Signal.LOW}
        assert Signal.from_int(2, fixed_width=4) == {3: Signal.LOW, 2: Signal.LOW, 1: Signal.HIGH, 0: Signal.LOW}
        with pytest.raises(ValueError):
            Signal.from_int(2, fixed_width=1)
        assert Signal.from_int(42) == {5: Signal.HIGH, 4: Signal.LOW, 3: Signal.HIGH, 2: Signal.LOW, 1: Signal.HIGH, 0: Signal.LOW}
        with pytest.raises(ValueError):
            Signal.from_int(42, fixed_width=3)
        assert Signal.from_int(-4) == {2: Signal.HIGH, 1: Signal.LOW, 0: Signal.LOW}
        assert Signal.from_int(-4, fixed_width=5) == {4: Signal.HIGH, 3: Signal.HIGH, 2: Signal.HIGH, 1: Signal.LOW, 0: Signal.LOW}


def test_to_int() -> None:
    assert Signal.to_int([]) == 0
    assert Signal.to_int([Signal.LOW]) == 0
    assert Signal.to_int([Signal.HIGH, Signal.LOW, Signal.HIGH, Signal.LOW, Signal.HIGH, Signal.LOW]) == 42
    assert Signal.to_int([Signal.HIGH, Signal.LOW, Signal.HIGH, Signal.LOW, Signal.HIGH, Signal.LOW], msb_first=False) == 21
    assert Signal.to_int([Signal.HIGH, Signal.LOW, Signal.HIGH, Signal.LOW, Signal.HIGH, Signal.LOW], signed=True) == -22
    assert Signal.to_int([Signal.HIGH, Signal.LOW, Signal.LOW, Signal.LOW], signed=True) == -8
    with pytest.raises(ValueError):
        Signal.to_int([Signal.FLOATING])
    with pytest.raises(ValueError):
        Signal.to_int([Signal.UNDEFINED])


def test_dict_to_int() -> None:
    assert Signal.dict_to_int({}) == 0
    assert Signal.dict_to_int({0: Signal.LOW}) == 0
    assert Signal.dict_to_int({3: Signal.HIGH}) == 8
    assert Signal.dict_to_int({5: Signal.HIGH, 4: Signal.LOW, 3: Signal.HIGH, 2: Signal.LOW, 1: Signal.HIGH, 0: Signal.LOW}) == 42
    assert Signal.dict_to_int({5: Signal.HIGH, 4: Signal.LOW, 3: Signal.HIGH, 2: Signal.LOW, 1: Signal.HIGH, 0: Signal.LOW}, msb_first=False) == 21
    assert Signal.dict_to_int({5: Signal.HIGH, 4: Signal.LOW, 3: Signal.HIGH, 2: Signal.LOW, 1: Signal.HIGH, 0: Signal.LOW}, signed=True) == -22
    assert Signal.dict_to_int({3: Signal.HIGH}, signed=True) == -8
    with pytest.raises(ValueError):
        Signal.dict_to_int({0: Signal.FLOATING})
    with pytest.raises(ValueError):
        Signal.dict_to_int({0: Signal.UNDEFINED})


def test_from_bin() -> None:
    with pytest.warns(
        DeprecationWarning,
        match=re.escape(
            "Signal.from_bin() is deprecated and will be removed in v1.0.0. Use SignalArray.from_bin() instead! SignalArray can be imported from 'netlist_carpentry.core.types'"
        ),
    ):
        assert Signal.from_bin('0') == {0: Signal.LOW}
        assert Signal.from_bin('1') == {0: Signal.HIGH}
        assert Signal.from_bin('10') == {1: Signal.HIGH, 0: Signal.LOW}
        assert Signal.from_bin('10', fixed_width=4) == {3: Signal.LOW, 2: Signal.LOW, 1: Signal.HIGH, 0: Signal.LOW}
        with pytest.raises(ValueError):
            Signal.from_bin('10', fixed_width=1)
        assert Signal.from_bin('10', msb_first=False) == {1: Signal.LOW, 0: Signal.HIGH}
        assert Signal.from_bin('101010') == {5: Signal.HIGH, 4: Signal.LOW, 3: Signal.HIGH, 2: Signal.LOW, 1: Signal.HIGH, 0: Signal.LOW}
        assert Signal.from_bin('0x0') == {2: Signal.LOW, 1: Signal.UNDEFINED, 0: Signal.LOW}

        with pytest.raises(ValueError):
            Signal.from_bin('0123')
        with pytest.raises(ValueError):
            Signal.from_bin('abc')


def test_to_bin() -> None:
    assert Signal.to_bin([]) == '0'
    assert Signal.to_bin([], pad_value='1') == '1'
    assert Signal.to_bin([Signal.LOW]) == '0'
    assert Signal.to_bin([Signal.HIGH, Signal.LOW, Signal.HIGH, Signal.LOW, Signal.HIGH, Signal.LOW]) == '101010'
    assert Signal.to_bin([Signal.HIGH, Signal.LOW, Signal.HIGH, Signal.LOW, Signal.HIGH, Signal.LOW], fixed_width=8) == '00101010'
    assert Signal.to_bin([Signal.HIGH, Signal.LOW, Signal.HIGH, Signal.LOW, Signal.HIGH, Signal.LOW], msb_first=False) == '010101'
    assert Signal.to_bin([Signal.HIGH, Signal.LOW, Signal.HIGH, Signal.LOW, Signal.HIGH, Signal.LOW], msb_first=False, fixed_width=8) == '01010100'
    with pytest.raises(ValueError):
        Signal.to_bin([Signal.FLOATING])
    with pytest.raises(ValueError):
        Signal.to_bin([Signal.UNDEFINED])


def test_dict_to_bin() -> None:
    assert Signal.dict_to_bin({}) == '0'
    assert Signal.dict_to_bin({}, pad_value='1') == '1'
    assert Signal.dict_to_bin({0: Signal.LOW}) == '0'
    assert Signal.dict_to_bin({3: Signal.HIGH}) == '1000'
    sigs = {5: Signal.HIGH, 4: Signal.LOW, 3: Signal.HIGH, 2: Signal.LOW, 1: Signal.HIGH, 0: Signal.LOW}
    assert Signal.dict_to_bin(sigs) == '101010'
    assert Signal.dict_to_bin(sigs, msb_first=False) == '010101'
    assert Signal.dict_to_bin(sigs, fixed_width=8) == '00101010'
    assert Signal.dict_to_bin(sigs, msb_first=False, fixed_width=8) == '01010100'
    with pytest.raises(ValueError):
        Signal.dict_to_bin({0: Signal.FLOATING})
    with pytest.raises(ValueError):
        Signal.dict_to_bin({0: Signal.UNDEFINED})


def test_twos_complement() -> None:
    assert Signal.twos_complement(6) == '010'  # 6: '110' => -6: '1010', but width is inferred as 3 only, so the "sign bit" is cut-off
    assert Signal.twos_complement(6, 4) == '1010'  # 6: '0110' => -6: '1010'
    assert Signal.twos_complement(-6) == '0110'  # -6: '1010' => 6: '0110'
    assert Signal.twos_complement(6, 8) == '11111010'  # 6: '00000110' => -6: '11111010'
    assert Signal.twos_complement(-6, 8) == '00000110'  # -6: '11111010' => 6: '00000110'
    assert Signal.twos_complement(6, 8, msb_first=False) == '01011111'  # 6: '00000110' => -6: '11111010' and then reverse
    assert Signal.twos_complement(-6, 8, msb_first=False) == '01100000'  # -6: '11111010' => 6: '00000110' and then reverse


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
