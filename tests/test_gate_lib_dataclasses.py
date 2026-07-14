import os

import pytest

from netlist_carpentry.utils.gate_lib_dataclasses import Parameters


def test_parameters_basics() -> None:
    p = Parameters()
    p2 = Parameters()
    with pytest.raises(KeyError):
        p['EXISTSNOTATTR']
    assert 'EXISTSNOTATTR' not in p
    assert len(p) == 0
    assert p == p2
    assert p.as_dict() == {}
    assert p.items() == []
    p['EXISTSNOTATTR'] = 'FOO'
    assert len(p) == 1
    assert 'EXISTSNOTATTR' in p
    assert p['EXISTSNOTATTR'] == 'FOO'
    assert p != p2
    assert p.as_dict() == {'EXISTSNOTATTR': 'FOO'}
    assert p.items() == [('EXISTSNOTATTR', 'FOO')]


def test_portparams() -> None:
    from netlist_carpentry.utils.gate_lib_dataclasses import PortParams

    p = PortParams()
    assert p.upto is None
    assert p.offset is None
    assert p.signed is None


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
