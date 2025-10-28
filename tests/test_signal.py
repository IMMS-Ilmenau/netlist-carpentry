import os

import pytest

from netlist_carpentry.core.signal import Signal


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
    assert Signal.LOW.invert() is Signal.HIGH
    assert Signal.HIGH.invert() is Signal.LOW
    assert Signal.FLOATING.invert() is Signal.UNDEFINED
    assert Signal.UNDEFINED.invert() is Signal.UNDEFINED


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
    assert Signal.from_int(0) == {0: Signal.LOW}
    assert Signal.from_int(1) == {0: Signal.HIGH}
    assert Signal.from_int(2) == {1: Signal.HIGH, 0: Signal.LOW}
    assert Signal.from_int(2, fixed_width=4) == {3: Signal.LOW, 2: Signal.LOW, 1: Signal.HIGH, 0: Signal.LOW}
    assert Signal.from_int(2, fixed_width=1) == {0: Signal.LOW}
    assert Signal.from_int(2, msb_first=False) == {1: Signal.LOW, 0: Signal.HIGH}
    assert Signal.from_int(42) == {5: Signal.HIGH, 4: Signal.LOW, 3: Signal.HIGH, 2: Signal.LOW, 1: Signal.HIGH, 0: Signal.LOW}
    assert Signal.from_int(42, fixed_width=3) == {2: Signal.LOW, 1: Signal.HIGH, 0: Signal.LOW}
    assert Signal.from_int(-4) == {2: Signal.HIGH, 1: Signal.LOW, 0: Signal.LOW}


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
    assert Signal.from_bin('0') == {0: Signal.LOW}
    assert Signal.from_bin('1') == {0: Signal.HIGH}
    assert Signal.from_bin('10') == {1: Signal.HIGH, 0: Signal.LOW}
    assert Signal.from_bin('10', fixed_width=4) == {3: Signal.LOW, 2: Signal.LOW, 1: Signal.HIGH, 0: Signal.LOW}
    assert Signal.from_bin('10', fixed_width=1) == {0: Signal.LOW}
    assert Signal.from_bin('10', msb_first=False) == {1: Signal.LOW, 0: Signal.HIGH}
    assert Signal.from_bin('101010') == {5: Signal.HIGH, 4: Signal.LOW, 3: Signal.HIGH, 2: Signal.LOW, 1: Signal.HIGH, 0: Signal.LOW}
    assert Signal.from_bin('101010', fixed_width=3) == {2: Signal.LOW, 1: Signal.HIGH, 0: Signal.LOW}
    assert Signal.from_bin('0x0') == {2: Signal.LOW, 1: Signal.UNDEFINED, 0: Signal.LOW}

    with pytest.raises(ValueError):
        Signal.from_bin('0123')
    with pytest.raises(ValueError):
        Signal.from_bin('abc')


def test_to_bin() -> None:
    assert Signal.to_bin([]) == '0'
    assert Signal.to_bin([Signal.LOW]) == '0'
    assert Signal.to_bin([Signal.HIGH, Signal.LOW, Signal.HIGH, Signal.LOW, Signal.HIGH, Signal.LOW]) == '101010'
    assert Signal.to_bin([Signal.HIGH, Signal.LOW, Signal.HIGH, Signal.LOW, Signal.HIGH, Signal.LOW], msb_first=False) == '010101'
    with pytest.raises(ValueError):
        Signal.to_bin([Signal.FLOATING])
    with pytest.raises(ValueError):
        Signal.to_bin([Signal.UNDEFINED])


def test_dict_to_bin() -> None:
    assert Signal.dict_to_bin({}) == '0'
    assert Signal.dict_to_bin({0: Signal.LOW}) == '0'
    assert Signal.dict_to_bin({3: Signal.HIGH}) == '1000'
    sigs = {5: Signal.HIGH, 4: Signal.LOW, 3: Signal.HIGH, 2: Signal.LOW, 1: Signal.HIGH, 0: Signal.LOW}
    assert Signal.dict_to_bin(sigs) == '101010'
    assert Signal.dict_to_bin(sigs, msb_first=False) == '010101'
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
