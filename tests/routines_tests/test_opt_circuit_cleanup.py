import os

import pytest

from netlist_carpentry import Circuit
from netlist_carpentry.routines import clean_circuit
from netlist_carpentry.routines.opt.circuit_cleanup import _clean_unused_single, clean_unused


def test_clean_circuit() -> None:
    c = Circuit(name='c')
    m1 = c.create_module('m1')
    m2 = c.create_module('m2')
    m3 = c.create_module('m3')
    m4 = c.create_module('m4')
    m5 = c.create_module('m5')

    c.set_top(m1)

    m1.create_instance(m2, 'I_m2')
    m2.create_instance(m3, 'I_m3')

    m4.create_instance(m5, 'I_m5')

    has_changed = clean_circuit(c)
    assert has_changed
    assert m1 in c
    assert m2 in c
    assert m3 in c
    assert m4 not in c
    assert m5 not in c

    has_changed = clean_circuit(c)
    assert not has_changed


def test_clean_unused() -> None:
    c = Circuit(name='c')
    m1 = c.create_module('m1')
    m2 = c.create_module('m2')
    m3 = c.create_module('m3')
    m4 = c.create_module('m4')
    m5 = c.create_module('m5')

    c.set_top(m1)

    m1.create_instance(m2, 'I_m2')
    m2.create_instance(m3, 'I_m3')

    m4.create_instance(m5, 'I_m5')

    has_changed = clean_unused(c)
    assert has_changed
    assert m1 in c
    assert m2 in c
    assert m3 in c
    assert m4 not in c
    assert m5 not in c

    has_changed = clean_unused(c)
    assert not has_changed


def test_clean_unused_single() -> None:
    c = Circuit(name='c')
    m1 = c.create_module('m1')
    m2 = c.create_module('m2')
    m3 = c.create_module('m3')
    m4 = c.create_module('m4')
    m5 = c.create_module('m5')

    c.set_top(m1)

    m1.create_instance(m2, 'I_m2')
    m2.create_instance(m3, 'I_m3')

    m4.create_instance(m5, 'I_m5')

    has_changed = _clean_unused_single(c)
    assert has_changed
    assert m1 in c
    assert m2 in c
    assert m3 in c
    assert m4 not in c
    assert m5 in c

    has_changed = _clean_unused_single(c)
    assert has_changed
    assert m1 in c
    assert m2 in c
    assert m3 in c
    assert m4 not in c
    assert m5 not in c

    has_changed = _clean_unused_single(c)
    assert not has_changed

    c.set_top(None)
    has_changed = _clean_unused_single(c)
    assert has_changed
    assert m1 not in c
    assert m2 in c
    assert m3 in c
    assert m4 not in c
    assert m5 not in c


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
