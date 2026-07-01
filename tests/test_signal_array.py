import os

import pytest

from netlist_carpentry import Signal
from netlist_carpentry.core.exceptions import InvalidSignalError
from netlist_carpentry.core.types import SignalArray


def test_basics() -> None:
    sa = SignalArray(signals={}, msb_first=False)
    assert isinstance(sa, SignalArray)
    assert sa.signals == {}
    assert sa.signed is False
    assert sa.msb_first is False
    assert sa.default_fill is Signal.UNDEFINED
    assert sa.size == 0
    assert sa.is_defined is False
    assert sa.is_undefined is False
    assert str(sa) == ''
    with pytest.raises(ValueError):
        int(sa)
    sa[0] = Signal.FLOATING
    assert sa.is_defined is False
    assert sa.is_undefined is True

    sa = SignalArray(signals={1: Signal.LOW, 2: Signal.HIGH}, signed=True, msb_first=True, default_fill=Signal.FLOATING)
    assert sa.signals == {0: Signal.FLOATING, 1: Signal.LOW, 2: Signal.HIGH}
    assert sa[0] is Signal.FLOATING
    with pytest.raises(KeyError, match=r"No index 3 in Signal array '10z' \(size 3\)!"):
        sa[3]
    assert sa.signed is True
    assert sa.msb_first is True
    assert sa.default_fill is Signal.FLOATING
    assert sa.size == 3
    assert sa.is_defined is False
    assert sa.is_undefined is False
    assert str(sa) == '10z'
    sa.msb_first = False
    assert str(sa) == 'z01'
    with pytest.raises(ValueError):
        int(sa)
    sa[0] = Signal.HIGH
    assert sa.is_defined is True
    assert str(sa) == '101'
    assert int(sa) == -3  # negative number, two's complement
    sa.signed = False
    assert str(sa) == '101'
    assert int(sa) == 5
    assert str(~sa) == '010'


def test_iter() -> None:
    sa = SignalArray.create('1010')
    idx = 0
    for k in sa:
        assert k == idx
        assert sa[k].value == '1010'[3 - k]  # MSB first
        idx += 1


def test_lshift() -> None:
    sa = SignalArray.create('0110')
    sb = SignalArray.create('0001')
    sc = SignalArray.from_int(-1, fixed_width=4)
    sd = SignalArray.from_int(-5, fixed_width=4)

    assert str(sa << sb) == '1100'
    assert int(sa << sb) == 12

    assert str(sa << 1) == '1100'
    assert int(sa << 1) == 12
    assert str(sa << sc) == '0011'  # 6 << -1
    assert int(sa << sc) == 3
    assert str(sc << sc) == '0111'  # -1 << -1
    assert int(sc << sc) == 7
    assert str(sc << 1) == '1110'  # -1 << 1
    assert int(sc << 1) == -2
    assert str(sd << 1) == '0110'  # -5 << 1
    assert int(sd << 1) == 6
    assert str(SignalArray.create('01xz') << 1) == '1xz0'
    with pytest.raises(InvalidSignalError):
        str(sa << SignalArray.create('01xz'))
    with pytest.raises(TypeError):
        str(sa << 'soos')


def test_rshift() -> None:
    sa = SignalArray.create('0110')
    sb = SignalArray.create('0001')
    sc = SignalArray.from_int(-1, fixed_width=4)
    sd = SignalArray.from_int(-5, fixed_width=4)

    assert str(sa >> sb) == '0011'
    assert int(sa >> sb) == 3

    assert str(sa >> 1) == '0011'
    assert int(sa >> 1) == 3
    assert str(sa >> sc) == '1100'  # 6 >> -1
    assert int(sa >> sc) == 12
    assert str(sc >> sc) == '1110'  # -1 >> -1
    assert int(sc >> sc) == -2
    assert str(sc >> 1) == '1111'  # -1 >> 1
    assert int(sc >> 1) == -1
    assert str(sd >> 1) == '1101'  # -5 >> 1
    assert int(sd >> 1) == -3
    assert str(SignalArray.create('xz10') >> 1) == '0xz1'
    with pytest.raises(InvalidSignalError):
        str(sa >> SignalArray.create('xz10'))
    with pytest.raises(TypeError):
        str(sa >> 'soos')


def test_invert() -> None:
    sa = SignalArray(signals={0: Signal.HIGH, 1: Signal.LOW})
    assert str(sa) == '01'
    assert str(~sa) == '10'

    sa = SignalArray(signals={0: Signal.FLOATING, 1: Signal.UNDEFINED})
    assert str(sa) == 'xz'
    assert str(~sa) == 'xx'  # Inverting z becomes x


def test_fill_gaps() -> None:
    sa = SignalArray(signals={})
    assert sa.signals == {}
    SignalArray.fill_gaps(sa.signals)
    assert sa.signals == {}

    sa = SignalArray(signals={})
    sa.signals = {1: Signal.LOW, 2: Signal.HIGH}
    assert sa.signals == {1: Signal.LOW, 2: Signal.HIGH}
    SignalArray.fill_gaps(sa.signals)
    assert sa.signals == {1: Signal.LOW, 2: Signal.HIGH, 0: Signal.UNDEFINED}

    sa = SignalArray(signals={})
    sa.signals = {1: Signal.LOW, 3: Signal.HIGH}
    assert sa.signals == {1: Signal.LOW, 3: Signal.HIGH}
    SignalArray.fill_gaps(sa.signals, Signal.FLOATING)
    assert sa.signals == {1: Signal.LOW, 3: Signal.HIGH, 0: Signal.FLOATING, 2: Signal.FLOATING}


def test_parseable() -> None:
    assert SignalArray.parsable(Signal.HIGH)
    assert SignalArray.parsable(True)
    assert SignalArray.parsable(1234)
    assert SignalArray.parsable(-1234)
    assert SignalArray.parsable('0110')
    assert SignalArray.parsable('xzzx')
    assert not SignalArray.parsable('0123')
    assert not SignalArray.parsable(['0', '1', '2', '3'])
    assert SignalArray.parsable(['0', '1', '1', '0'])
    assert SignalArray.parsable({0: '0', 1: '1', 2: '1', 3: '0'})
    assert not SignalArray.parsable({0: '0', -1: '1', -2: '1', -3: '0'})
    assert not SignalArray.parsable({'0': '0', '1': '1', '2': '1', '3': '0'})

    assert SignalArray.parsable([0, 1, '0', '1', 'x', 'z', 'X', 'Z', True, False, Signal.LOW, Signal.HIGH, Signal.FLOATING, Signal.UNDEFINED])
    assert SignalArray.parsable(
        {
            0: 0,
            1: 1,
            2: '0',
            3: '1',
            4: 'x',
            5: 'z',
            6: 'X',
            7: 'Z',
            8: True,
            9: False,
            10: Signal.LOW,
            11: Signal.HIGH,
            12: Signal.FLOATING,
            13: Signal.UNDEFINED,
        }
    )


def test_create_dict() -> None:
    array = SignalArray.create({})

    assert isinstance(array, SignalArray)
    assert array.signals == {}

    array = SignalArray.create({0: Signal.HIGH, 1: Signal.LOW, 2: Signal.HIGH, 3: Signal.LOW})

    assert isinstance(array, SignalArray)
    assert array.signals == {0: Signal.HIGH, 1: Signal.LOW, 2: Signal.HIGH, 3: Signal.LOW}

    array = SignalArray.create({1: 0, 2: '1', 3: False}, default_fill=Signal.HIGH)

    assert isinstance(array, SignalArray)
    assert array.default_fill is Signal.HIGH
    assert array.signals == {0: Signal.HIGH, 1: Signal.LOW, 2: Signal.HIGH, 3: Signal.LOW}

    with pytest.raises(InvalidSignalError):
        SignalArray.create({-1: Signal.HIGH})
    with pytest.raises(InvalidSignalError):
        SignalArray.create({'1': Signal.HIGH})


def test_create_list() -> None:
    array = SignalArray.create([])

    assert isinstance(array, SignalArray)
    assert array.signals == {}
    array = SignalArray.create([Signal.HIGH, Signal.LOW, Signal.HIGH, Signal.LOW])

    assert isinstance(array, SignalArray)
    assert array.signals == {0: Signal.HIGH, 1: Signal.LOW, 2: Signal.HIGH, 3: Signal.LOW}

    array = SignalArray.create([Signal.HIGH, 0, '1', False])

    assert isinstance(array, SignalArray)
    assert array.signals == {0: Signal.HIGH, 1: Signal.LOW, 2: Signal.HIGH, 3: Signal.LOW}


def test_create_int() -> None:
    array = SignalArray.create(0)

    assert isinstance(array, SignalArray)
    assert array.signals == {0: Signal.LOW}
    assert array.signed is False

    array = SignalArray.create(-4)

    assert isinstance(array, SignalArray)
    assert array.signals == {2: Signal.HIGH, 1: Signal.LOW, 0: Signal.LOW}
    assert str(array) == '100'  # -4
    assert array.signed is True


def test_create_str() -> None:
    array = SignalArray.create('')

    assert isinstance(array, SignalArray)
    assert array.signals == {}
    assert array.signed is False

    array = SignalArray.create('0')

    assert isinstance(array, SignalArray)
    assert array.signals == {0: Signal.LOW}
    assert array.signed is False

    array = SignalArray.create('100')

    assert isinstance(array, SignalArray)
    assert array.signals == {2: Signal.HIGH, 1: Signal.LOW, 0: Signal.LOW}
    assert str(array) == '100'  # -4

    array = SignalArray.create('xz')
    assert array.signals == {1: Signal.UNDEFINED, 0: Signal.FLOATING}

    with pytest.raises(ValueError):
        SignalArray.create('abc')


def test_from_int() -> None:
    sa = SignalArray.from_int(10)
    assert sa.signed is False
    assert int(sa) == 10
    assert str(sa) == '1010'

    sa = SignalArray.from_int(10, msb_first=False)
    assert sa.signed is False
    assert int(sa) == 10
    assert str(sa) == '0101'

    sa = SignalArray.from_int(10, fixed_width=5)
    assert sa.signed is False
    assert int(sa) == 10
    assert str(sa) == '01010'

    sa = SignalArray.from_int(1)
    assert sa.signed is False
    assert int(sa) == 1
    assert str(sa) == '1'

    sa = SignalArray.from_int(-1)
    assert sa.signed is True
    assert int(sa) == -1
    assert str(sa) == '1'

    sa = SignalArray.from_int(-3)
    assert sa.signed is True
    assert int(sa) == -3
    assert str(sa) == '101'

    sa = SignalArray.from_int(-3, fixed_width=3)
    assert sa.signed is True
    assert int(sa) == -3
    assert str(sa) == '101'

    with pytest.raises(ValueError):
        SignalArray.from_int(-3, fixed_width=2)

    sa = SignalArray.from_int(-3, fixed_width=2, truncate=True)
    assert sa.signed is True
    assert int(sa) == 1
    assert str(sa) == '01'

    sa = SignalArray.from_int(-3, fixed_width=5)
    assert sa.signed is True
    assert int(sa) == -3
    assert str(sa) == '11101'


def test_from_bin() -> None:
    sa = SignalArray.from_bin('1010')
    assert sa.signed is False
    assert int(sa) == 10
    assert str(sa) == '1010'

    sa = SignalArray.from_bin('1010', msb_first=False)
    assert sa.signed is False
    assert int(sa) == 5
    assert str(sa) == '1010'

    sa = SignalArray.from_bin('01010', fixed_width=5, signed=True)
    assert sa.signed is True
    assert int(sa) == 10
    assert str(sa) == '01010'

    sa = SignalArray.from_bin('1')
    assert sa.signed is False
    assert int(sa) == 1
    assert str(sa) == '1'

    sa = SignalArray.from_bin('1', signed=True)
    assert sa.signed is True
    assert int(sa) == -1
    assert str(sa) == '1'

    sa = SignalArray.from_bin('101', signed=True)
    assert sa.signed is True
    assert int(sa) == -3
    assert str(sa) == '101'

    sa = SignalArray.from_bin('101', signed=True, fixed_width=3)
    assert sa.signed is True
    assert int(sa) == -3
    assert str(sa) == '101'

    with pytest.raises(ValueError):
        SignalArray.from_bin('101', signed=True, fixed_width=2)

    sa = SignalArray.from_bin('101', signed=True, fixed_width=2, truncate=True)
    assert sa.signed is True
    assert int(sa) == 1
    assert str(sa) == '01'

    sa = SignalArray.from_bin('101', signed=True, fixed_width=5)
    assert sa.signed is True
    assert int(sa) == -3
    assert str(sa) == '11101'


def test_from_int_dicts() -> None:
    assert SignalArray.from_int(0).signals == {0: Signal.LOW}
    assert SignalArray.from_int(1).signals == {0: Signal.HIGH}
    assert SignalArray.from_int(2).signals == {1: Signal.HIGH, 0: Signal.LOW}
    assert SignalArray.from_int(2, fixed_width=4).signals == {3: Signal.LOW, 2: Signal.LOW, 1: Signal.HIGH, 0: Signal.LOW}
    with pytest.raises(ValueError):
        SignalArray.from_int(2, fixed_width=1)
    assert SignalArray.from_int(2, msb_first=False).signals == {0: Signal.LOW, 1: Signal.HIGH}  # Only str changes
    assert SignalArray.from_int(42).signals == {5: Signal.HIGH, 4: Signal.LOW, 3: Signal.HIGH, 2: Signal.LOW, 1: Signal.HIGH, 0: Signal.LOW}
    with pytest.raises(ValueError):
        SignalArray.from_int(42, fixed_width=3).signals
    assert SignalArray.from_int(-4).signals == {2: Signal.HIGH, 1: Signal.LOW, 0: Signal.LOW}
    assert SignalArray.from_int(-4, fixed_width=5).signals == {4: Signal.HIGH, 3: Signal.HIGH, 2: Signal.HIGH, 1: Signal.LOW, 0: Signal.LOW}


def test_from_bin_dicts() -> None:
    assert SignalArray.from_bin('0').signals == {0: Signal.LOW}
    assert SignalArray.from_bin('1').signals == {0: Signal.HIGH}
    assert SignalArray.from_bin('10').signals == {1: Signal.HIGH, 0: Signal.LOW}
    assert SignalArray.from_bin('10', fixed_width=4).signals == {3: Signal.LOW, 2: Signal.LOW, 1: Signal.HIGH, 0: Signal.LOW}
    with pytest.raises(ValueError):
        SignalArray.from_bin('10', fixed_width=1)
    assert SignalArray.from_bin('10', fixed_width=1, truncate=True).signals == {0: Signal.LOW}
    assert SignalArray.from_bin('10', msb_first=False).signals == {1: Signal.LOW, 0: Signal.HIGH}
    assert SignalArray.from_bin('101010').signals == {5: Signal.HIGH, 4: Signal.LOW, 3: Signal.HIGH, 2: Signal.LOW, 1: Signal.HIGH, 0: Signal.LOW}
    with pytest.raises(ValueError):
        SignalArray.from_bin('101010', fixed_width=3)
    assert SignalArray.from_bin('101010', fixed_width=3, truncate=True).signals == {2: Signal.LOW, 1: Signal.HIGH, 0: Signal.LOW}
    assert SignalArray.from_bin('0x0').signals == {2: Signal.LOW, 1: Signal.UNDEFINED, 0: Signal.LOW}

    with pytest.raises(ValueError):
        SignalArray.from_bin('0123')
    with pytest.raises(ValueError):
        SignalArray.from_bin('abc')


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
