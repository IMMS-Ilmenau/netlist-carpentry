# mypy: disable-error-code="call-overload"

import os

import pytest

import netlist_carpentry.routines.check.fanout_analysis as fa
from netlist_carpentry import Circuit
from netlist_carpentry.core.exceptions import UnsupportedOperationError
from netlist_carpentry.routines import fanout


@pytest.fixture()
def connected_circuit() -> Circuit:
    from utils import connected_circuit

    return connected_circuit()


def test_fanout(connected_circuit: Circuit) -> None:
    with pytest.raises(UnsupportedOperationError):
        fanout(connected_circuit, sort_by='coolness')

    fanout_path = fanout(connected_circuit, sort_by='path')
    assert len(fanout_path) == 20
    all_wires = list(connected_circuit['test_module1'].wires.values()) + list(connected_circuit['wrapper'].wires.values())
    for w in all_wires:
        assert w.path in fanout_path
        if w.name == 'en':
            assert fanout_path[w.path] == 0
        elif w.name == 'wire_xor':
            assert fanout_path[w.path] == 2
        else:
            assert fanout_path[w.path] == 1

    fanout_nr = fanout(connected_circuit, sort_by='number')
    assert len(fanout_nr) == 3
    assert len(fanout_nr[0]) == 1
    assert len(fanout_nr[1]) == 18
    assert len(fanout_nr[2]) == 1


def test_fanout_module(connected_circuit: Circuit) -> None:
    m = connected_circuit['test_module1']
    with pytest.raises(UnsupportedOperationError):
        fa.fanout_module(m, sort_by='coolness')

    fanout = fa.fanout_module(m, sort_by='path')
    assert len(fanout) == 12

    fanout_nr = fa.fanout_module(m, sort_by='number')
    assert len(fanout_nr) == 3
    assert len(fanout_nr[0]) == 1
    assert len(fanout_nr[1]) == 10
    assert len(fanout_nr[2]) == 1


def test_fanout_by_path(connected_circuit: Circuit) -> None:
    m = connected_circuit['test_module1']
    fanout = fa.fanout_by_path(m)
    assert len(fanout) == 12
    for w in m.wires.values():
        assert w.path in fanout
        if w.name == 'en':
            assert fanout[w.path] == 0
        elif w.name == 'wire_xor':
            assert fanout[w.path] == 2
        else:
            assert fanout[w.path] == 1

    and_inst = m.instances['and_inst']
    m.disconnect(and_inst.ports['B'])
    m.connect(m.wires['in1'], and_inst.ports['B'])
    fanout = fa.fanout_by_path(m)
    assert len(fanout) == 12
    assert fanout[m.wires['in1'].path] == 2
    assert fanout[m.wires['in2'].path] == 0

    m.wires['in1'].create_wire_segments(3, 1)
    fanout = fa.fanout_by_path(m)
    assert len(fanout) == 15
    assert m.wires['in1'].path not in fanout
    assert fanout[m.wires['in1'][0].path] == 2
    assert fanout[m.wires['in1'][1].path] == 0
    assert fanout[m.wires['in1'][2].path] == 0
    assert fanout[m.wires['in1'][3].path] == 0


def test_fanout_by_number(connected_circuit: Circuit) -> None:
    m = connected_circuit['test_module1']
    with pytest.raises(UnsupportedOperationError):
        fa.fanout_module(m, sort_by='coolness')

    fanout = fa.fanout_by_number(m)
    assert len(fanout) == 3
    assert len(fanout[0]) == 1
    assert len(fanout[1]) == 10
    assert len(fanout[2]) == 1
    for w in m.wires.values():
        if w.name == 'en':
            assert w.path in fanout[0]
        elif w.name == 'wire_xor':
            assert w.path in fanout[2]
        else:
            assert w.path in fanout[1]

    m.wires['in1'].create_wire_segments(3, 1)
    fanout = fa.fanout_by_number(m)
    assert len(fanout) == 3
    assert len(fanout[0]) == 4
    assert m.wires['in1'].path not in fanout
    assert m.wires['in1'][0].path in fanout[1]
    assert m.wires['in1'][1].path in fanout[0]
    assert m.wires['in1'][2].path in fanout[0]
    assert m.wires['in1'][3].path in fanout[0]


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
